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
        self.authorization_status = 200
        self.oauth_error = "invalid_grant"
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
            if not refreshing and self.authorization_status != 200:
                return httpx.Response(self.authorization_status, json={
                    "error": self.oauth_error,
                    "error_description": "sensitive provider fixture must never echo",
                    "access_token": "fake-secret-in-error-response",
                })
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


def test_loopback_shows_safe_error_stage_and_persists_only_identifiers(siwc):
    from app.ai.chatgpt_diagnostics import OAUTH_DIAGNOSTIC
    c, r, f = siwc
    started, p = begin(siwc)
    with httpx.Client(trust_env=False, timeout=3) as local:
        response = local.get(started["redirect_uri"], params={
            "state": p["state"], "code": "sensitive-fake-code",
            "error_description": "<script>untrusted fixture</script>",
        })
    assert response.status_code == 400
    assert "chatgpt_invalid_client" in response.text and "đăng ký động" in response.text
    assert "sensitive-fake-code" not in response.text and p["state"] not in response.text
    assert "untrusted fixture" not in response.text
    assert "history.replaceState" in response.text
    assert "unsafe-inline" not in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "no-referrer"
    status = c.get("/api/ai/chatgpt/status").json()
    assert status["last_error"]["stage"] == "client_registration"
    assert r.ai.chatgpt._get(OAUTH_DIAGNOSTIC) == {
        "code": "chatgpt_invalid_client", "stage": "client_registration"}
    reopened = ChatGPTConnection(r.db, r.ai.vault, httpx.MockTransport(f), clock=lambda: f.time)
    try:
        after = reopened.status()
        assert after["authorization_status"] == "failed"
        assert after["last_error"]["code"] == "chatgpt_invalid_client"
        assert after["live_verification"] == "pending_live_verification"
    finally:
        reopened.close()


@pytest.mark.parametrize("provider_code,expected", [
    ("invalid_grant", "chatgpt_oauth_invalid_grant"),
    ("invalid_client", "chatgpt_oauth_invalid_client"),
    ("invalid_request", "chatgpt_oauth_invalid_request"),
    ("invalid_scope", "chatgpt_oauth_invalid_scope"),
    ("unrecognized-sensitive-value", "chatgpt_request_rejected"),
])
def test_token_exchange_failures_have_safe_actionable_diagnostics(provider_code, expected, siwc):
    c, r, f = siwc
    f.authorization_status = 400
    f.oauth_error = provider_code
    _, p = begin(siwc)
    with pytest.raises(GSCError) as error:
        r.ai.chatgpt.callback({"state": p["state"], "code": "sensitive-fake-code",
                               "client_id": "oaiapp_test"})
    assert error.value.code == expected
    status = c.get("/api/ai/chatgpt/status")
    assert status.json()["last_error"]["code"] == expected
    assert status.json()["last_error"]["stage"] == "token_exchange"
    assert all(value not in status.text for value in (
        "sensitive provider fixture", "fake-secret", "sensitive-fake-code", "unrecognized-sensitive-value"))
    assert not r.ai.vault.get(TOKENS)
    assert len([call for call in f.calls if call[1] == TOKEN]) == 1


def test_shutdown_during_authorization_is_diagnosable_after_restart(siwc):
    c, r, f = siwc
    begin(siwc)
    r.ai.chatgpt.close()
    reopened = ChatGPTConnection(r.db, r.ai.vault, httpx.MockTransport(f), clock=lambda: f.time)
    try:
        assert not reopened.status()["pending_authorization"]
        assert reopened.status()["last_error"]["code"] == "chatgpt_oauth_interrupted"
        r.ai.chatgpt = reopened
        begin(siwc)
        assert reopened.status()["last_error"] is None
    finally:
        reopened.close()


def test_real_vault_adapter_handles_windows_sized_tokens_and_can_disconnect_corruption(siwc, monkeypatch):
    from app.gsc.vault import CredentialVault
    from test_vault import SimulatedWinVault
    c, r, f = siwc
    backend = SimulatedWinVault()
    vault = CredentialVault()
    monkeypatch.setattr(vault, "_backend", lambda: backend)
    r.ai.vault = r.ai.chatgpt.vault = vault
    request = r.ai.chatgpt.http.request

    def long_tokens(method, url, **kwargs):
        result = request(method, url, **kwargs)
        if url == TOKEN:
            result.update(access_token="fake-access-" + "a" * 6000,
                          refresh_token="fake-refresh-" + "b" * 3000)
        return result

    r.ai.chatgpt.http.request = long_tokens
    login(siwc, False)
    assert r.ai.chatgpt.status()["status"] == "connected_authorized"
    manifest = json.loads(backend.values[TOKENS])
    del backend.values[f"{TOKENS}.part.{manifest['slot']}.0"]
    assert not r.ai.chatgpt.status()["secure_storage_available"]
    result = c.post("/api/ai/chatgpt/disconnect", json={"confirm": True, "revoke": True})
    assert result.status_code == 200 and result.json()["local_credentials_removed"]
    assert not result.json()["remote_revoked"]
    assert not any(key.startswith(TOKENS) for key in backend.values)


def test_native_vault_write_error_is_reported_at_storage_step_without_token_leak(siwc, monkeypatch):
    from app.gsc.vault import CredentialVault
    from test_vault import SimulatedWinVault
    c, r, f = siwc
    backend = SimulatedWinVault()
    vault = CredentialVault()
    monkeypatch.setattr(vault, "_backend", lambda: backend)
    r.ai.vault = r.ai.chatgpt.vault = vault
    _, p = begin(siwc)
    backend.fail_write = lambda key: key.startswith(TOKENS)
    with pytest.raises(GSCError):
        r.ai.chatgpt.callback({"state": p["state"], "code": "sensitive-fake-code",
                               "client_id": "oaiapp_test"})
    status = c.get("/api/ai/chatgpt/status")
    assert status.json()["last_error"]["code"] == "secure_storage_unavailable"
    assert status.json()["last_error"]["stage"] == "credential_storage"
    assert "fake-secret" not in status.text and not vault.get(TOKENS)


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


@pytest.mark.parametrize("changes,reason", [
    ({"iss": "https://not-openai.example/private-value"}, "issuer_mismatch"),
    ({"aud": "private-client"}, "audience_mismatch"),
    ({"aud": ["oaiapp_test", 123]}, "audience_mismatch"),
    ({"aud": ["oaiapp_test", "other"]}, "authorized_party_mismatch"),
    ({"azp": "private-client"}, "authorized_party_mismatch"),
    ({"exp": 1}, "token_expired"),
    ({"exp": True}, "invalid_timestamp"),
    ({"iat": "private-time"}, "invalid_timestamp"),
    ({"nbf": True}, "invalid_timestamp"),
    ({"sub": ""}, "subject_mismatch"),
    ({"nonce": None}, "nonce_missing"),
    ({"nonce": "private-wrong-nonce"}, "nonce_mismatch"),
    ({"nonce": "mã-không-khớp"}, "nonce_mismatch"),
])
def test_id_token_safe_specific_validation_reasons(private_key, changes, reason):
    issuer = Issuer(private_key)
    token = issuer.jwt({"nonce": "expected-nonce", **changes})
    with pytest.raises(GSCError) as caught:
        validate_id_token(token, issuer.keys, "oaiapp_test", "expected-nonce", clock=issuer.time)
    error = caught.value
    assert error.code == "chatgpt_invalid_id_token" and error.status == 401
    assert error.token_reason == reason
    assert token not in str(error) and "private-" not in str(error)
    assert "expected-nonce" not in str(error)


@pytest.mark.parametrize("field,offset,accepted,reason", [
    ("iat", 30.001, True, None),
    ("iat", 60, True, None),
    ("iat", 60.001, False, "issued_in_future"),
    ("nbf", 60, True, None),
    ("nbf", 60.001, False, "not_yet_valid"),
    ("exp", -59.999, True, None),
    ("exp", -60, False, "token_expired"),
    ("exp", -3600, False, "token_expired"),
])
def test_oidc_clock_leeway_is_bounded_and_consistent(private_key, field, offset, accepted, reason):
    issuer = Issuer(private_key)
    token = issuer.jwt({field: issuer.time + offset, "nonce": "expected-nonce"})
    if accepted:
        result = validate_id_token(token, issuer.keys, "oaiapp_test", "expected-nonce", clock=issuer.time)
        assert result["sub"] == "test-account" and "nonce" not in result
    else:
        with pytest.raises(GSCError) as caught:
            validate_id_token(token, issuer.keys, "oaiapp_test", "expected-nonce", clock=issuer.time)
        assert caught.value.token_reason == reason


@pytest.mark.parametrize("mutation,reason", [
    ("missing", "missing_token"),
    ("format", "malformed_token"),
    ("algorithm", "unsupported_algorithm"),
    ("header_url", "unsupported_header"),
    ("kid", "missing_key_id"),
    ("unknown_kid", "signing_key_unavailable"),
    ("duplicate_key", "signing_key_unavailable"),
    ("key_material", "invalid_signing_key"),
    ("key_ops", "invalid_signing_key"),
    ("signature", "signature_mismatch"),
])
def test_id_token_key_and_signature_diagnostics(private_key, mutation, reason):
    issuer = Issuer(private_key)
    token = issuer.jwt()
    h, b, sig = token.split(".")
    header = json.loads(b64(h))
    if mutation == "missing":
        token = None
    elif mutation == "format":
        token = "not.a.valid.jwt"
    elif mutation in ("algorithm", "header_url", "kid", "unknown_kid"):
        if mutation == "algorithm":
            header["alg"] = "none"
        elif mutation == "header_url":
            header["jku"] = "https://not-openai.example/keys"
        elif mutation == "kid":
            header.pop("kid")
        else:
            header["kid"] = "not-in-jwks"
        token = encoded(json.dumps(header).encode()) + "." + b + "." + sig
    elif mutation == "duplicate_key":
        issuer.keys["keys"] *= 2
    elif mutation == "key_material":
        issuer.keys["keys"][0]["n"] = "not-valid!"
    elif mutation == "key_ops":
        issuer.keys["keys"][0]["key_ops"] = ["sign"]
    else:
        token = h + "." + b + "." + encoded(b"invalid signature")
    with pytest.raises(GSCError) as caught:
        validate_id_token(token, issuer.keys, "oaiapp_test", clock=issuer.time)
    assert caught.value.token_reason == reason
    assert "not-openai.example" not in str(caught.value)


def test_unrelated_malformed_jwks_entry_does_not_break_valid_signature(private_key):
    issuer = Issuer(private_key)
    issuer.keys["keys"] = [None, "unrelated", *issuer.keys["keys"], {"kty": "EC"}]
    assert validate_id_token(issuer.jwt(), issuer.keys, "oaiapp_test", clock=issuer.time)["sub"] == "test-account"


def test_small_clock_skew_completes_full_oauth_callback(siwc):
    c, r, issuer = siwc
    # Reproduces the old >30-second iat rejection even with a valid signature,
    # issued client, nonce and an otherwise fresh token.
    issuer.jwt_changes = {"iat": issuer.time + 45, "nbf": issuer.time + 45}
    login(siwc)
    assert c.get("/api/ai/chatgpt/status").json()["status"] == "connected_authorized"
    assert len([call for call in issuer.calls if call[1] == TOKEN]) == 1


@pytest.mark.parametrize("changes,reason", [
    ({"aud": "private-audience-do-not-persist"}, "audience_mismatch"),
    ({"iat": 99999999999}, "issued_in_future"),
    ({"nonce": None}, "nonce_missing"),
])
def test_loopback_token_reason_survives_restart_without_sensitive_claims(siwc, changes, reason):
    from app.ai.chatgpt_diagnostics import OAUTH_DIAGNOSTIC
    c, r, issuer = siwc
    started, pending = begin(siwc)
    # The mocked issuer normally echoes nonce; override jwt after that step to
    # exercise an actual missing nonce as well as claim mismatches.
    original_jwt = issuer.jwt
    issuer.jwt = lambda *args, **kwargs: original_jwt(changes, **kwargs) if "nonce" not in changes else original_jwt(changes)
    with httpx.Client(trust_env=False, timeout=5) as local:
        response = local.get(started["redirect_uri"], params={
            "state": pending["state"], "code": "sensitive-code-do-not-persist",
            "client_id": "oaiapp_test",
        })
    assert response.status_code == 401 and reason in response.text
    assert "Chi tiết kiểm tra" in response.text
    assert pending["state"] not in response.text and "private-audience" not in response.text
    assert "sensitive-code-do-not-persist" not in response.text
    expected = {"code": "chatgpt_invalid_id_token", "stage": "id_token_validation", "reason": reason}
    assert r.ai.chatgpt._get(OAUTH_DIAGNOSTIC) == expected
    status = c.get("/api/ai/chatgpt/status").json()
    assert status["last_error"]["reason"] == reason
    assert status["status"] == "not_connected" and not r.ai.vault.get(TOKENS)
    assert not any(call[1] in (RESOURCE + "/models", RESOURCE + "/responses") for call in issuer.calls)
    reopened = ChatGPTConnection(r.db, r.ai.vault, httpx.MockTransport(issuer), clock=lambda: issuer.time)
    try:
        assert reopened.status()["last_error"] == status["last_error"]
    finally:
        reopened.close()


def test_unknown_token_diagnostic_is_never_persisted_or_echoed():
    from app.ai.chatgpt_diagnostics import diagnostic
    message = diagnostic("chatgpt_invalid_id_token", "id_token_validation", "sensitive-token-text")
    assert "reason" not in message and "sensitive-token-text" not in json.dumps(message)
    assert "reason" not in diagnostic("chatgpt_network", reason="nonce_missing")


class CatalogChunks(httpx.SyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False
        self.bytes_read = 0

    def __iter__(self):
        for chunk in self.chunks:
            self.bytes_read += len(chunk)
            yield chunk

    def close(self):
        self.closed = True


@pytest.mark.parametrize("method,url,expected", [
    ("GET", RESOURCE + "/models", None),
    ("POST", TOKEN, "chatgpt_response_limit"),
    ("GET", DISCOVERY, "chatgpt_response_limit"),
    ("GET", JWKS, "chatgpt_response_limit"),
])
def test_large_json_allowance_is_scoped_to_model_catalog(method, url, expected):
    content = json.dumps({"models": [], "extra": "x" * (MAX_JSON_BYTES + 1000)}).encode()
    stream = CatalogChunks([content[:200001], content[200001:]])
    transport = ChatGPTTransport(httpx.MockTransport(lambda req: httpx.Response(200, stream=stream)))
    if expected:
        with pytest.raises(GSCError) as error:
            transport.request(method, url)
        assert error.value.code == expected
    else:
        assert transport.request(method, url)["models"] == []
    assert stream.closed


@pytest.mark.parametrize("over_limit", [False, True])
def test_model_catalog_decoded_byte_limit_boundary(over_limit):
    prefix, suffix = b'{"models":[],"extra":"', b'"}'
    padding = MAX_MODEL_CATALOG_BYTES - len(prefix) - len(suffix) + int(over_limit)
    # Split the valid JSON into chunks; no reliance on Content-Length.
    content = prefix + b"x" * padding + suffix
    stream = CatalogChunks(content[i:i + 65535] for i in range(0, len(content), 65535))
    transport = ChatGPTTransport(httpx.MockTransport(lambda req: httpx.Response(200, stream=stream)))
    if over_limit:
        with pytest.raises(GSCError) as error:
            transport.request("GET", RESOURCE + "/models", token="fake-access")
        assert error.value.code == "chatgpt_models_response_limit"
    else:
        assert transport.request("GET", RESOURCE + "/models")["models"] == []
    assert stream.closed


def test_compressed_catalog_is_bounded_by_decoded_size():
    import gzip
    compressed = gzip.compress(b"x" * (MAX_MODEL_CATALOG_BYTES + 1))
    assert len(compressed) < MAX_JSON_BYTES
    stream = CatalogChunks([compressed])
    transport = ChatGPTTransport(httpx.MockTransport(lambda req: httpx.Response(
        200, headers={"content-encoding": "gzip", "content-length": str(len(compressed))}, stream=stream)))
    with pytest.raises(GSCError) as error:
        transport.request("GET", RESOURCE + "/models")
    assert error.value.code == "chatgpt_models_response_limit" and stream.closed


def test_model_read_timeout_is_distinct_from_response_size(monkeypatch):
    from types import SimpleNamespace
    import app.ai.chatgpt_protocol as protocol
    clock_values = iter([0, JSON_READ_SECONDS + 1])
    monkeypatch.setattr(protocol, "time", SimpleNamespace(monotonic=lambda: next(clock_values)))
    stream = CatalogChunks([b'{"models":[]}'])
    transport = ChatGPTTransport(httpx.MockTransport(lambda req: httpx.Response(200, stream=stream)))
    with pytest.raises(GSCError) as error:
        transport.request("GET", RESOURCE + "/models")
    assert error.value.code == "chatgpt_response_timeout" and error.value.status == 504
    assert stream.closed


def test_large_model_catalog_completes_oauth_and_stores_only_picker_fields(siwc):
    c, r, issuer = siwc
    issuer.model_rows[0]["capabilities"] = {"instructions": "Mô tả model. " * 100000}
    assert len(json.dumps({"models": issuer.model_rows}).encode()) > MAX_JSON_BYTES
    login(siwc, False)
    status = c.get("/api/ai/chatgpt/status").json()
    assert status["authorization_status"] == "completed" and status["plan_usage_authorized"]
    assert status["model_listing_status"] == "ready" and status["last_error"] is None
    assert status["models"] == [{"slug": "plan-test-model", "display_name": "Model tài khoản thử nghiệm"}]
    assert status["selected_model"] is None
    cached = r.ai.chatgpt._get(MODELS)
    assert len(json.dumps(cached).encode()) < 1000 and "instructions" not in json.dumps(cached)
    assert "capabilities" not in json.dumps(status)
    assert c.patch("/api/ai/chatgpt/model", json={"slug": "plan-test-model"}).status_code == 200
    assert r.ai.chatgpt.preflight()["model"] == "plan-test-model"
    assert not any(call[1] == RESOURCE + "/responses" for call in issuer.calls)


def test_model_fetch_failure_keeps_login_and_success_clears_saved_error(siwc):
    from app.ai.chatgpt_diagnostics import OAUTH_DIAGNOSTIC
    c, r, issuer = siwc
    issuer.models_status = 503
    login(siwc, False)
    before = c.get("/api/ai/chatgpt/status").json()
    session_id = before["connection_id"]
    assert before["status"] == "connected_authorized" and before["authorization_status"] == "completed"
    assert before["model_listing_status"] == "failed" and before["last_error"]["stage"] == "model_listing"
    reopened = ChatGPTConnection(r.db, r.ai.vault, httpx.MockTransport(issuer), clock=lambda: issuer.time)
    try:
        # Reading status, including after restart, never reissues the model call.
        count = len(issuer.calls)
        after_restart = reopened.status()
        assert after_restart["authorization_status"] == "completed" and after_restart["model_listing_status"] == "failed"
        assert after_restart["last_error"] == before["last_error"]
        assert len(issuer.calls) == count
        issuer.models_status = 200
        issuer.model_rows[0]["extra"] = "x" * (MAX_JSON_BYTES + 1)
        refreshed = c.post("/api/ai/chatgpt/models/refresh")
        assert refreshed.status_code == 200
        ready = refreshed.json()
        assert ready["connection_id"] == session_id and ready["status"] == "connected_authorized"
        assert ready["model_listing_status"] == "ready" and ready["last_error"] is None
        assert r.ai.chatgpt._get(OAUTH_DIAGNOSTIC) == {}
        assert reopened.status()["last_error"] is None
        assert len([call for call in issuer.calls if call[1] == TOKEN]) == 1
        assert not any(call[1] == RESOURCE + "/responses" for call in issuer.calls)
    finally:
        reopened.close()


def test_manual_model_failure_is_visible_and_does_not_destroy_last_good_catalog(siwc):
    c, r, issuer = siwc
    login(siwc)
    previous = r.ai.chatgpt.status()
    issuer.models_status = 429
    assert c.post("/api/ai/chatgpt/models/refresh").status_code == 429
    failed = c.get("/api/ai/chatgpt/status").json()
    assert failed["status"] == "connected_authorized" and failed["model_listing_status"] == "failed"
    assert failed["models"] == previous["models"] and failed["selected_model"] == previous["selected_model"]
    assert failed["last_error"]["code"] == "chatgpt_quota" and failed["last_error"]["stage"] == "model_listing"
    issuer.models_status = 200
    recovered = c.post("/api/ai/chatgpt/models/refresh").json()
    assert recovered["last_error"] is None and recovered["selected_model"] == "plan-test-model"


@pytest.mark.parametrize("rows", [[], [{"visibility": "hidden", "slug": "hidden"}]])
def test_empty_visible_catalog_is_distinct_from_failed_loading(siwc, rows):
    c, r, issuer = siwc
    issuer.model_rows = rows
    login(siwc, False)
    status = r.ai.chatgpt.status()
    assert status["model_listing_status"] == "empty" and status["last_error"] is None
    assert status["models"] == [] and not status["models_stale"]
    assert status["selected_model"] is None and status["status"] == "connected_authorized"
    with pytest.raises(GSCError) as error:
        r.ai.chatgpt.preflight()
    assert error.value.code == "chatgpt_model_unavailable"


def test_successful_catalog_refresh_removes_unavailable_selection_without_replacement(siwc):
    c, r, issuer = siwc
    login(siwc)
    issuer.model_rows = [{"visibility": "list", "slug": "other-model", "display_name": "Other"}]
    refreshed = c.post("/api/ai/chatgpt/models/refresh").json()
    assert refreshed["model_listing_status"] == "ready" and refreshed["selected_model"] is None
    with pytest.raises(GSCError):
        r.ai.chatgpt.preflight()


def test_callback_warns_about_model_failure_without_claiming_oauth_failed(siwc):
    c, r, issuer = siwc
    issuer.models_status = 503
    started, pending = begin(siwc)
    with httpx.Client(trust_env=False, timeout=5) as local:
        response = local.get(started["redirect_uri"], params={
            "state": pending["state"], "code": "fake-sensitive-code",
            "client_id": "oaiapp_test",
        })
    assert response.status_code == 200 and "Đã hoàn tất đăng nhập" in response.text
    assert "chưa tải được danh sách model" in response.text and "Lấy danh sách model ChatGPT" in response.text
    assert "fake-sensitive-code" not in response.text and pending["state"] not in response.text
    assert r.ai.chatgpt.status()["model_listing_status"] == "failed"


def test_oversized_catalog_is_retryable_with_existing_session(siwc):
    c, r, issuer = siwc
    original = issuer.__call__
    def handler(request):
        if str(request.url) == RESOURCE + "/models":
            stream = CatalogChunks(b"x" * JSON_CHUNK_BYTES for _ in range(MAX_MODEL_CATALOG_BYTES // JSON_CHUNK_BYTES + 2))
            return httpx.Response(200, stream=stream)
        return original(request)
    r.ai.chatgpt.http = ChatGPTTransport(httpx.MockTransport(handler))
    login(siwc, False)
    failed = r.ai.chatgpt.status()
    assert failed["model_listing_status"] == "failed" and failed["status"] == "connected_authorized"
    assert failed["last_error"]["code"] == "chatgpt_models_response_limit"
    r.ai.chatgpt.http = ChatGPTTransport(httpx.MockTransport(issuer))
    success = c.post("/api/ai/chatgpt/models/refresh").json()
    assert success["last_error"] is None and success["model_listing_status"] == "ready"
    assert success["connection_id"] == failed["connection_id"]
    assert len([call for call in issuer.calls if call[1] == TOKEN]) == 1


@pytest.mark.parametrize("rows", [None, {"unexpected": "not-a-list"}, [{"visibility": "hidden"}] * 1001])
def test_invalid_or_excessive_catalog_does_not_become_an_empty_success(siwc, rows):
    c, r, issuer = siwc
    issuer.model_rows = rows
    login(siwc, False)
    status = r.ai.chatgpt.status()
    assert status["status"] == "connected_authorized" and status["model_listing_status"] == "failed"
    assert status["last_error"]["code"] == "chatgpt_models_invalid"
    assert status["models"] == [] and r.ai.vault.get(TOKENS)["access_token"]


def test_model_recovery_does_not_erase_an_unrelated_oauth_error(siwc):
    from app.ai.chatgpt_diagnostics import OAUTH_DIAGNOSTIC
    c, r, issuer = siwc
    login(siwc, False)
    r.ai.chatgpt._record_oauth_error("chatgpt_invalid_id_token", "id_token_validation", "audience_mismatch")
    previous = r.ai.chatgpt.status()["last_error"]
    assert c.post("/api/ai/chatgpt/models/refresh").status_code == 200
    assert r.ai.chatgpt.status()["last_error"] == previous
    assert r.ai.chatgpt._get(OAUTH_DIAGNOSTIC)["reason"] == "audience_mismatch"


def test_model_network_diagnostic_does_not_instruct_relogin():
    from app.ai.chatgpt_diagnostics import diagnostic
    error = diagnostic("chatgpt_network", "model_listing")
    assert "Lấy danh sách model ChatGPT" in error["detail"]
    assert "đăng nhập mới" not in error["detail"]
