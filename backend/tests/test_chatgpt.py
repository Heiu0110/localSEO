"""SIWC contract tests use generated RSA keys and mock HTTPS, never real credentials/quota."""

import base64, json, time, hashlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlsplit, urlencode
from unittest.mock import Mock
import httpx, pytest
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from sqlalchemy import select
from test_ai import env, conv, MemoryVault
from app.ai.chatgpt import ChatGPTConnection, TOKENS, REGISTRATION, MODEL, MODELS
from app.ai.chatgpt_protocol import *
from app.ai.schemas import MessageCreate
from app.ai.common import uid
from app.ai.models import AIMessage, AIUsage
from app.ai.provider import KEY_NAME
from app.gsc.errors import GSCError


def encoded(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@pytest.fixture(scope="module")
def private_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class Issuer:
    def __init__(self, key):
        self.key = key
        self.connection = None
        self.time = time.time()
        self.granted = SCOPES
        self.calls = []
        self.refreshes = 0
        self.mode = "ok"
        self.nonce_override = None
        self.jwt_changes = {}
        self.refresh_status = 200
        self.models_status = 200
        self.inference_status = 200
        self.model_rows = [
            {
                "slug": "plan-test-model",
                "display_name": "Model tài khoản thử nghiệm",
                "visibility": "list",
            },
            {"slug": "hidden", "display_name": "Hidden", "visibility": "hidden"},
        ]
        numbers = key.public_key().public_numbers()
        self.keys = {
            "keys": [
                {
                    "kid": "test-key",
                    "kty": "RSA",
                    "alg": "RS256",
                    "use": "sig",
                    "n": encoded(
                        numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big")
                    ),
                    "e": encoded(numbers.e.to_bytes(3, "big")),
                }
            ]
        }

    def jwt(self, changes=None, nonce=None):
        claims = {
            "iss": ISSUER,
            "aud": "oaiapp_test",
            "exp": self.time + 3600,
            "iat": self.time,
            "sub": "test-account",
            "email": "fixture@example.test",
            "name": "Tài khoản mô phỏng",
            **self.jwt_changes,
            **(changes or {}),
        }
        if nonce:
            claims["nonce"] = nonce
        h = encoded(json.dumps({"alg": "RS256", "kid": "test-key"}).encode())
        b = encoded(json.dumps(claims).encode())
        sig = self.key.sign((h + "." + b).encode(), padding.PKCS1v15(), hashes.SHA256())
        return h + "." + b + "." + encoded(sig)

    def __call__(self, request):
        url = str(request.url)
        body = (
            parse_qs(request.content.decode())
            if request.headers.get("content-type", "").startswith(
                "application/x-www-form-urlencoded"
            )
            else json.loads(request.content) if request.content else None
        )
        self.calls.append((request.method, url, dict(request.headers), body))
        if url == DISCOVERY:
            return httpx.Response(
                200,
                json={
                    "issuer": ISSUER,
                    "authorization_endpoint": AUTHORIZE,
                    "token_endpoint": TOKEN,
                    "jwks_uri": JWKS,
                    "code_challenge_methods_supported": ["S256"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "revocation_endpoint": ISSUER + "/oauth/revoke",
                },
            )
        if url == JWKS:
            return httpx.Response(200, json=self.keys)
        if url == TOKEN:
            refreshing = body["grant_type"] == ["refresh_token"]
            if refreshing:
                self.refreshes += 1
            if refreshing and self.refresh_status != 200:
                return httpx.Response(
                    self.refresh_status, json={"error": "invalid_grant"}
                )
            pending = (
                self.connection.pending_nonce
                if hasattr(self.connection, "pending_nonce")
                else None
            )
            result = {
                "access_token": "fake-access-" + str(self.refreshes),
                "refresh_token": "fake-refresh-" + str(self.refreshes),
                "token_type": "Bearer",
                "expires_in": 3600,
                "scope": self.granted,
            }
            if not refreshing:
                result["id_token"] = self.jwt(nonce=self.nonce_override or pending)
            return httpx.Response(200, json=result)
        if url == RESOURCE + "/models":
            return httpx.Response(self.models_status, json={"models": self.model_rows})
        if url == ISSUER + "/oauth/revoke":
            return httpx.Response(200)
        if url == RESOURCE + "/responses":
            if self.inference_status != 200:
                return httpx.Response(
                    self.inference_status,
                    json={"error": {"code": "never_echo_raw_fake_secret"}},
                )
            if self.mode == "tool":
                output = [
                    {
                        "type": "function_call",
                        "name": "get_gsc_overview",
                        "call_id": "test-call",
                        "arguments": '{"days":28}',
                    }
                ]
                self.mode = "ok"
            else:
                text = json.dumps(
                    {
                        "summary": "Phân tích theo bằng chứng trong ngữ cảnh.",
                        "findings": [],
                        "recommendations": [],
                        "limitations": ["Mock provider, không phải live OAuth."],
                        "next_step": "Rà soát dữ liệu.",
                    },
                    ensure_ascii=False,
                )
                output = [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": text}],
                    }
                ]
            events = [
                {"type": "response.output_text.delta", "delta": '{"summary":'},
                {
                    "type": "response.completed",
                    "response": {
                        "id": "test-response",
                        "status": "completed",
                        "output": output,
                        "usage": {"input_tokens": 30, "output_tokens": 20},
                    },
                },
            ]
            if self.mode == "incomplete":
                events[-1] = {
                    "type": "response.incomplete",
                    "response": {"status": "incomplete"},
                }
            elif self.mode == "failed":
                events[-1] = {
                    "type": "response.failed",
                    "response": {
                        "error": {
                            "code": "unexpected",
                            "message": "fake secret must not echo",
                        }
                    },
                }
            elif self.mode == "quota_event":
                events[-1] = {"type": "error", "error": {"code": "usage_limit_reached"}}
            elif self.mode == "interrupted":
                events = events[:1]
            content = "".join(
                "event: "
                + e["type"]
                + "\r\ndata: "
                + json.dumps(e, ensure_ascii=False)
                + "\r\n\r\n"
                for e in events
            ).encode()
            return httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=content
            )
        raise AssertionError("Unexpected outbound URL: " + url)


@pytest.fixture
def siwc(env, private_key):
    c, r = env
    fake = Issuer(private_key)
    r.ai.chatgpt = ChatGPTConnection(
        r.db, r.ai.vault, httpx.MockTransport(fake), clock=lambda: fake.time
    )
    fake.connection = r.ai.chatgpt
    return c, r, fake


def begin(siwc):
    c, r, f = siwc
    response = c.post(
        "/api/ai/chatgpt/connect",
        json={"eligibility_acknowledged": True, "localhost_acknowledged": True},
    )
    assert response.status_code == 200, response.text
    r.ai.chatgpt.pending_nonce = r.ai.chatgpt.pending["nonce"]
    return response.json(), r.ai.chatgpt.pending.copy()


def login(siwc, select=True):
    c, r, f = siwc
    started, pending = begin(siwc)
    r.ai.chatgpt.callback(
        {"state": pending["state"], "code": "fake-code", "client_id": "oaiapp_test"}
    )
    if select and DIRECT in f.granted:
        response = c.patch("/api/ai/chatgpt/model", json={"slug": "plan-test-model"})
        assert response.status_code == 200, response.text
    return started, pending


def test_dynamic_registration_pkce_listener_nonce_and_no_client_secret(siwc):
    c, r, f = siwc
    started, pending = begin(siwc)
    params = parse_qs(urlsplit(started["authorization_url"]).query)
    assert params["client_id"] == ["dynamic_agent_client"] and params[
        "agent_name_hint"
    ] == ["LocalSEO"]
    assert params["ext_agent_host_id"][0].startswith("urn:uuid:")
    assert params["code_challenge"] == [
        encoded(hashlib.sha256(pending["verifier"].encode()).digest())
    ]
    assert params["code_challenge_method"] == ["S256"] and params["nonce"] == [
        pending["nonce"]
    ]
    assert params["resource"] == [RESOURCE] and set(params["scope"][0].split()) == set(
        SCOPES.split()
    )
    assert started["redirect_uri"].startswith("http://127.0.0.1:") and started[
        "redirect_uri"
    ].endswith("/auth/callback")
    # Listener is already accepting connections, with bad state rejected and session retained.
    with httpx.Client(trust_env=False, timeout=3) as local:
        response = local.get(started["redirect_uri"] + "?state=wrong&code=do-not-echo")
    assert (
        response.status_code == 400
        and "do-not-echo" not in response.text
        and r.ai.chatgpt.pending
    )
    r.ai.chatgpt.callback(
        {"state": pending["state"], "code": "fake-code", "client_id": "oaiapp_test"}
    )
    exchange = next(x for x in f.calls if x[1] == TOKEN)[3]
    assert (
        exchange["client_id"] == ["oaiapp_test"]
        and exchange["code_verifier"] == [pending["verifier"]]
        and exchange["redirect_uri"] == [started["redirect_uri"]]
    )
    assert "client_secret" not in exchange
    assert r.ai.vault.get(REGISTRATION)["client_id"] == "oaiapp_test"
    assert c.get("/api/ai/chatgpt/status").json()["status"] == "connected_authorized"


def test_actual_loopback_callback_completes_and_replay_fails_without_code_echo(siwc):
    c, r, f = siwc
    started, p = begin(siwc)
    with httpx.Client(trust_env=False, timeout=3) as local:
        response = local.get(
            started["redirect_uri"]
            + "?"
            + urlencode(
                {
                    "state": p["state"],
                    "code": "fake-code-sensitive",
                    "client_id": "oaiapp_test",
                }
            )
        )
    assert response.status_code == 200 and "fake-code-sensitive" not in response.text
    with pytest.raises(GSCError):
        r.ai.chatgpt.callback(
            {
                "state": p["state"],
                "code": "fake-code-sensitive",
                "client_id": "oaiapp_test",
            }
        )
    assert len([call for call in f.calls if call[1] == TOKEN]) == 1


@pytest.mark.parametrize(
    "failure", ["state", "expiry", "denied", "client", "missing_client"]
)
def test_oauth_rejects_invalid_callbacks_before_exchange(failure, siwc):
    c, r, f = siwc
    _, p = begin(siwc)
    query = {"state": p["state"], "code": "fake-code", "client_id": "oaiapp_test"}
    if failure == "state":
        query["state"] = "wrong"
    if failure == "expiry":
        f.time += 601
    if failure == "denied":
        query["error"] = "access_denied"
    if failure == "client":
        query["client_id"] = "dynamic_agent_client"
    if failure == "missing_client":
        query.pop("client_id")
    with pytest.raises(GSCError):
        r.ai.chatgpt.callback(query)
    assert not any(call[1] == TOKEN for call in f.calls) and not r.ai.vault.get(TOKENS)


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://evil.example"},
        {"aud": "wrong-client"},
        {"exp": 1},
        {"sub": ""},
        {"nbf": 99999999999},
        {"aud": ["oaiapp_test", "other"], "azp": "other"},
    ],
)
def test_signed_id_token_claim_validation(changes, siwc):
    c, r, f = siwc
    f.jwt_changes = changes
    _, p = begin(siwc)
    with pytest.raises(GSCError, match="ID token"):
        r.ai.chatgpt.callback(
            {"state": p["state"], "code": "fake-code", "client_id": "oaiapp_test"}
        )
    assert not r.ai.vault.get(TOKENS)


def test_nonce_signature_alg_and_jwks_endpoint_validation(siwc):
    c, r, f = siwc
    _, p = begin(siwc)
    token = f.jwt(nonce="wrong-nonce")
    with pytest.raises(GSCError):
        validate_id_token(token, f.keys, "oaiapp_test", p["nonce"], clock=f.time)
    h, b, sig = token.split(".")
    with pytest.raises(GSCError):
        validate_id_token(
            h + "." + b + "." + encoded(b"bad"), f.keys, "oaiapp_test", clock=f.time
        )
    with pytest.raises(GSCError):
        validate_id_token(
            encoded(b'{"alg":"none","kid":"test-key"}') + "." + b + "." + sig,
            f.keys,
            "oaiapp_test",
            clock=f.time,
        )
    with pytest.raises(GSCError):
        discovery_metadata(
            {
                "issuer": ISSUER,
                "authorization_endpoint": AUTHORIZE,
                "token_endpoint": TOKEN,
                "jwks_uri": "http://127.0.0.1/keys",
            }
        )


def test_connected_without_plan_permission_never_fetches_models_or_infers(siwc):
    c, r, f = siwc
    f.granted = "openid profile email offline_access"
    login(siwc, False)
    status = c.get("/api/ai/chatgpt/status").json()
    assert (
        status["status"] == "connected_not_authorized"
        and not status["plan_usage_authorized"]
    )
    assert c.post("/api/ai/chatgpt/models/refresh").status_code == 403
    with pytest.raises(GSCError):
        r.ai.chatgpt.preflight()
    assert not any(
        x[1] in (RESOURCE + "/models", RESOURCE + "/responses") for x in f.calls
    )


def test_refresh_rotation_single_flight_no_extra_scopes_and_registration_reuse(siwc):
    c, r, f = siwc
    login(siwc)
    f.time += 3601
    with ThreadPoolExecutor(max_workers=4) as pool:
        credentials = list(pool.map(lambda _: r.ai.chatgpt.credentials(), range(4)))
    assert (
        f.refreshes == 1
        and len({x["refresh_token"] for x in credentials}) == 1
        and credentials[0]["refresh_token"] == "fake-refresh-1"
    )
    refresh = next(
        x[3]
        for x in f.calls
        if x[1] == TOKEN and x[3]["grant_type"] == ["refresh_token"]
    )
    assert (
        refresh["client_id"] == ["oaiapp_test"]
        and refresh["resource"] == [RESOURCE]
        and "scope" not in refresh
    )
    r.ai.chatgpt.disconnect()
    started, _ = begin(siwc)
    assert parse_qs(urlsplit(started["authorization_url"]).query)["client_id"] == [
        "oaiapp_test"
    ]


@pytest.mark.parametrize("reason", ["refresh_expired", "revoked", "scope_removed"])
def test_expired_revoked_or_removed_permission_blocks_plan_usage(reason, siwc):
    c, r, f = siwc
    login(siwc)
    f.time += 3601
    if reason == "refresh_expired":
        f.time += 31 * 86400
    elif reason == "revoked":
        f.refresh_status = 400
    else:
        f.granted = "openid profile"
    with pytest.raises(GSCError):
        r.ai.chatgpt.credentials()
    status = r.ai.chatgpt.status()
    assert status["status"] in ("reauthorization_required", "connected_not_authorized")
    assert not any(x[1] == RESOURCE + "/responses" for x in f.calls)


def test_model_selection_visibility_and_disappearance_no_api_model_fallback(siwc):
    c, r, f = siwc
    login(siwc, False)
    status = r.ai.chatgpt.status()
    assert [m["slug"] for m in status["models"]] == ["plan-test-model"] and status[
        "selected_model"
    ] is None
    assert c.patch("/api/ai/chatgpt/model", json={"slug": "hidden"}).status_code == 409
    assert (
        c.patch("/api/ai/chatgpt/model", json={"slug": "gpt-4.1-mini"}).status_code
        == 409
    )
    assert (
        c.patch("/api/ai/chatgpt/model", json={"slug": "plan-test-model"}).status_code
        == 200
    )
    f.model_rows = []
    f.time += 301
    with pytest.raises(GSCError):
        r.ai.chatgpt.preflight()


def test_sse_uses_plan_token_allowlist_and_requires_terminal_completed(siwc):
    c, r, f = siwc
    login(siwc)
    p = r.ai.chatgpt.preflight()
    deltas = []
    result = r.ai.chatgpt.respond(
        {
            "model": p["model"],
            "input": [{"role": "user", "content": "test"}],
            "store": True,
            "stream": False,
            "max_output_tokens": 3,
            "metadata": {"secret": "must not forward"},
            "temperature": 1,
            "previous_response_id": "old",
            "tools": [],
        },
        p["connection_id"],
        deltas.append,
    )
    request = next(x for x in f.calls if x[1] == RESOURCE + "/responses")
    assert request[2]["authorization"] == "Bearer fake-access-0"
    assert (
        set(request[3]) == {"model", "input", "store", "stream"}
        and request[3]["store"] is False
        and request[3]["stream"] is True
    )
    assert result["status"] == "completed" and deltas == ['{"summary":']
    assert r.ai.chatgpt.status()["live_verification"] == "verified_for_this_session"


@pytest.mark.parametrize("mode", ["incomplete", "failed", "interrupted", "quota_event"])
def test_stream_failure_or_early_end_is_not_success(mode, siwc):
    c, r, f = siwc
    login(siwc)
    f.mode = mode
    p = r.ai.chatgpt.preflight()
    with pytest.raises(GSCError) as error:
        r.ai.chatgpt.respond({"model": p["model"], "input": []}, p["connection_id"])
    assert "fake secret" not in error.value.message
    assert r.ai.chatgpt.status()["live_verification"] == "pending_live_verification"
    assert len([x for x in f.calls if x[1] == RESOURCE + "/responses"]) == 1


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_provider_errors_no_retry_or_paid_fallback(status, siwc):
    c, r, f = siwc
    login(siwc)
    f.inference_status = status
    r.ai.vault.put(KEY_NAME, {"api_key": "fake-api-key-not-for-siwc"})
    r.ai.provider_factory = Mock(
        side_effect=AssertionError("API key fallback forbidden")
    )
    conversation = conv((c, r), provider="chatgpt")
    flight = r.ai.chatgpt.preflight()
    request = MessageCreate(
        content="Phân tích SEO",
        provider="chatgpt",
        request_key=uid(),
        acknowledge_external_processing=True,
        approved_model=flight["model"],
        approved_connection_id=flight["connection_id"],
    )
    m = r.ai.start(conversation["id"], request, submit=False)
    r.ai.run(m["id"])
    with r.db.session() as s:
        assert s.get(AIMessage, m["id"]).status == "failed"
        usage = s.scalar(select(AIUsage).where(AIUsage.message_id == m["id"]))
        assert (
            usage.provider == "chatgpt"
            and usage.status == "unknown"
            and usage.estimated_cost_usd is None
        )
    assert (
        not r.ai.provider_factory.called
        and len([x for x in f.calls if x[1] == RESOURCE + "/responses"]) == 1
    )


def test_existing_agent_uses_siwc_function_tools_and_preserves_evidence_and_usage(siwc):
    c, r, f = siwc
    login(siwc)
    f.mode = "tool"
    r.ai.provider_factory = Mock(side_effect=AssertionError("No API key"))
    conversation = conv((c, r), provider="chatgpt")
    flight = r.ai.chatgpt.preflight()
    with pytest.raises(GSCError):
        r.ai.start(
            conversation["id"],
            MessageCreate(content="SEO", provider="chatgpt", request_key=uid()),
            submit=False,
        )
    with pytest.raises(GSCError):
        r.ai.start(
            conversation["id"],
            MessageCreate(
                content="SEO",
                provider="chatgpt",
                request_key=uid(),
                acknowledge_external_processing=True,
                approved_model="wrong",
                approved_connection_id=flight["connection_id"],
            ),
            submit=False,
        )
    m = r.ai.start(
        conversation["id"],
        MessageCreate(
            content="Phân tích hiệu suất",
            provider="chatgpt",
            request_key=uid(),
            acknowledge_external_processing=True,
            approved_model=flight["model"],
            approved_connection_id=flight["connection_id"],
        ),
        submit=False,
    )
    r.ai.run(m["id"])
    with r.db.session() as s:
        done = s.get(AIMessage, m["id"])
        assert done.status == "completed", done.data
        usage = list(s.scalars(select(AIUsage).where(AIUsage.message_id == m["id"])))
        assert len(usage) == 2 and all(
            u.provider == "chatgpt"
            and u.input_tokens == 30
            and u.estimated_cost_usd is None
            for u in usage
        )
    detail = c.get(
        f"/api/ai/conversations/{conversation['id']}?project_id=xuong-may"
    ).json()
    assert any(
        e["source_type"] == "demo_gsc" for e in detail["messages"][-1]["evidence"]
    )
    assert c.get("/api/ai/usage").json()["daily_used_estimate_usd"] == 0
    assert not r.ai.provider_factory.called


def test_disconnect_revoke_token_secrecy_csrf_and_missing_vault(siwc):
    c, r, f = siwc
    login(siwc)
    status = c.get("/api/ai/chatgpt/status")
    assert "fake-access" not in status.text and "fake-refresh" not in status.text
    with r.db.engine.connect() as conn:
        settings = " ".join(
            str(row) for row in conn.exec_driver_sql("select * from app_settings").all()
        )
        assert "fake-access" not in settings and "fake-refresh" not in settings
    assert (
        c.post(
            "/api/ai/chatgpt/connect", json={}, headers={"X-CSRF-Token": "bad"}
        ).status_code
        == 403
    )
    assert (
        c.post(
            "/api/ai/chatgpt/connect",
            json={},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    result = c.post(
        "/api/ai/chatgpt/disconnect", json={"confirm": True, "revoke": True}
    )
    assert result.status_code == 200 and result.json()["remote_revoked"]
    assert not r.ai.vault.get(TOKENS) and r.ai.vault.get(REGISTRATION)
    assert c.get("/api/ai/chatgpt/status").json()["status"] == "not_connected"
    r.ai.vault.get = Mock(
        side_effect=GSCError("secure_storage_unavailable", "No vault", 503)
    )
    assert c.get("/api/ai/chatgpt/status").json()["secure_storage_available"] is False
    assert (
        c.post(
            "/api/ai/chatgpt/connect",
            json={"eligibility_acknowledged": True, "localhost_acknowledged": True},
        ).status_code
        == 503
    )


def test_eligibility_review_required_and_no_license_or_provider_settings_rewritten(
    siwc,
):
    c, r, f = siwc
    assert c.post("/api/ai/chatgpt/connect", json={}).status_code == 409
    assert f.calls == [] and r.ai.chatgpt.server is None
    state = c.get("/api/ai/chatgpt/status")
    assert (
        state.headers["cache-control"] == "no-store"
        and state.json()["eligibility"]["status"] == "pending_live_verification"
    )
    assert (
        not state.json()["full_preview_limitations_verified"]
        and state.json()["quota"]["remaining"] is None
    )
    old = c.get("/api/ai/settings").json()
    login(siwc)
    assert c.get("/api/ai/settings").json() == old


def test_stream_fragmentation_utf8_size_limit_and_hosted_tools(siwc):
    c, r, f = siwc
    login(siwc)
    flight = r.ai.chatgpt.preflight()

    class Bytes(httpx.SyncByteStream):
        def __iter__(self):
            stream = (
                "data: "
                + json.dumps(
                    {"type": "response.output_text.delta", "delta": "Tiếng Việt"},
                    ensure_ascii=False,
                )
                + "\r\n\r\n"
                + "data: "
                + json.dumps(
                    {
                        "type": "response.completed",
                        "response": {"status": "completed", "output": []},
                    }
                )
                + "\r\n\r\n"
            ).encode()
            for i in range(0, len(stream), 3):
                yield stream[i : i + 3]

    transport = ChatGPTTransport(
        httpx.MockTransport(
            lambda req: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, stream=Bytes()
            )
        )
    )
    deltas = []
    result = transport.inference(
        "fake-token", {"model": flight["model"], "input": []}, deltas.append
    )
    assert result["status"] == "completed" and deltas == ["Tiếng Việt"]
    with pytest.raises(GSCError):
        transport.inference(
            "fake-token",
            {"model": flight["model"], "input": [], "tools": [{"type": "web_search"}]},
        )
    oversized = ChatGPTTransport(
        httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                headers={"content-type": "text/event-stream"},
                content=b"x" * (512 * 1024 + 1),
            )
        )
    )
    with pytest.raises(GSCError):
        oversized.inference("fake-token", {"model": flight["model"], "input": []})


def test_connection_switch_after_consent_blocks_queued_request(siwc):
    c, r, f = siwc
    login(siwc)
    flight = r.ai.chatgpt.preflight()
    conversation = conv((c, r), provider="chatgpt")
    queued = r.ai.start(
        conversation["id"],
        MessageCreate(
            content="SEO",
            provider="chatgpt",
            request_key=uid(),
            acknowledge_external_processing=True,
            approved_model=flight["model"],
            approved_connection_id=flight["connection_id"],
        ),
        submit=False,
    )
    login(siwc)
    r.ai.run(queued["id"])
    with r.db.session() as s:
        assert s.get(AIMessage, queued["id"]).status == "failed"
    assert not any(x[1] == RESOURCE + "/responses" for x in f.calls)


@pytest.mark.parametrize("status", [401, 403, 429, 503])
def test_errors_after_stream_open_are_classified_without_success(status):
    content = (
        "data: "
        + json.dumps({"type": "response.output_text.delta", "delta": "partial"})
        + "\n\n"
        + "data: "
        + json.dumps(
            {
                "type": "error",
                "error": {"status": status, "message": "sensitive raw payload"},
            }
        )
        + "\n\n"
    ).encode()
    transport = ChatGPTTransport(
        httpx.MockTransport(
            lambda req: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=content
            )
        )
    )
    with pytest.raises(GSCError) as error:
        transport.inference("fake-token", {"model": "model", "input": []})
    assert (
        error.value.status == status
        and "sensitive raw payload" not in error.value.message
    )


def test_refresh_id_token_cannot_switch_subject(siwc):
    c, r, f = siwc
    login(siwc)
    f.time += 3601
    original = r.ai.chatgpt.http.request

    def request(method, url, **kwargs):
        result = original(method, url, **kwargs)
        if url == TOKEN and kwargs.get("form", {}).get("grant_type") == "refresh_token":
            result["id_token"] = f.jwt({"sub": "different-account"})
        return result

    r.ai.chatgpt.http.request = request
    with pytest.raises(GSCError):
        r.ai.chatgpt.credentials()
    assert r.ai.chatgpt.status()["status"] == "reauthorization_required"


def test_token_endpoint_redirect_is_rejected_without_forwarding_credentials(siwc):
    c, r, f = siwc
    _, pending = begin(siwc)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(302, headers={"location": "https://evil.example/steal"})

    r.ai.chatgpt.http = ChatGPTTransport(httpx.MockTransport(handler))
    with pytest.raises(GSCError):
        r.ai.chatgpt.callback(
            {"state": pending["state"], "code": "fake-code", "client_id": "oaiapp_test"}
        )
    assert calls == [TOKEN] and not r.ai.vault.get(TOKENS)


@pytest.mark.parametrize(
    "changes",
    [
        {"token_type": 1},
        {"access_token": "bad\nheader"},
        {"refresh_token": "bad\rtoken"},
        {"expires_in": "3600"},
    ],
)
def test_malformed_token_response_fails_with_safe_error(changes, siwc):
    c, r, f = siwc
    result = {
        "token_type": "Bearer",
        "access_token": "fake-access",
        "refresh_token": "fake-refresh",
        "expires_in": 3600,
        "scope": SCOPES,
        **changes,
    }
    with pytest.raises(GSCError) as error:
        r.ai.chatgpt._credentials(result, "oaiapp_test", {"sub": "test-account"})
    assert error.value.code == "chatgpt_invalid_tokens" and not r.ai.vault.get(TOKENS)


def test_malformed_stream_error_is_safe_protocol_failure():
    content = b'data: {"type":"response.failed","response":"not-an-object"}\n\n'
    transport = ChatGPTTransport(
        httpx.MockTransport(
            lambda req: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=content
            )
        )
    )
    with pytest.raises(GSCError) as error:
        transport.inference("fake-token", {"model": "model", "input": []})
    assert error.value.code == "chatgpt_invalid_sse"


def test_host_identity_is_stable_in_vault_but_not_cloned_with_sqlite(siwc):
    c, r, f = siwc
    original = r.ai.chatgpt._host()
    assert r.ai.chatgpt._host() == original
    another = ChatGPTConnection(r.db, MemoryVault())
    try:
        assert another._host() != original
        assert another._host() == another._host()
    finally:
        another.close()


def test_missing_initial_granted_scopes_is_connected_but_not_plan_authorized(siwc):
    c, r, f = siwc
    original = r.ai.chatgpt.http.request

    def request(method, url, **kwargs):
        result = original(method, url, **kwargs)
        if url == TOKEN:
            result.pop("scope", None)
        return result

    r.ai.chatgpt.http.request = request
    login(siwc, False)
    status = r.ai.chatgpt.status()
    assert (
        status["status"] == "connected_not_authorized"
        and status["granted_scopes"] == []
    )
    assert not any(x[1] == RESOURCE + "/models" for x in f.calls)
