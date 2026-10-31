"""SIWC protocol per the official handoff supplied 2026-10-29; no API-key fallback.

Only fixed OpenAI hosts, RS256 ID tokens and bounded Responses SSE are accepted.
Full preview limitations and live eligibility still need local verification.
"""

import base64
import json
import math
import re
import secrets
import time
from urllib.parse import urlsplit
import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from .common import fail
from .chatgpt_diagnostics import MESSAGES, ID_TOKEN_REASONS
from app.gsc.errors import GSCError

ISSUER = "https://auth.openai.com"
AUTHORIZE = ISSUER + "/api/accounts/authorize"
TOKEN = ISSUER + "/api/accounts/oauth/token"
DISCOVERY = ISSUER + "/.well-known/openid-configuration"
JWKS = ISSUER + "/.well-known/jwks.json"
RESOURCE = "https://api.openai.com/v1"
DIRECT = "chatgpt.tokens.use.direct"
SCOPES = "openid profile email offline_access resource.invoke " + DIRECT
MAX_BYTES = 1024 * 1024
# Bounded OIDC clock leeway, applied consistently to exp/iat/nbf. No expiry
# bypass and no reliance on unverified claims or provider Date headers.
ID_TOKEN_CLOCK_SKEW_SECONDS = 60


def json_object(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    value = json.loads(
        raw,
        object_pairs_hook=unique,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")),
    )
    if not isinstance(value, dict):
        raise ValueError("object required")
    return value


def b64(raw):
    if not isinstance(raw, str) or len(raw) > 65536:
        raise ValueError()
    return base64.b64decode(raw + "=" * (-len(raw) % 4), altchars=b"-_", validate=True)


class _InvalidIDToken(ValueError):
    def __init__(self, reason):
        self.reason = reason


def _require_token(condition, reason):
    if not condition:
        raise _InvalidIDToken(reason)


def _verified_id_token(token, jwks, client_id, nonce, subject, current):
    _require_token(isinstance(token, str) and bool(token), "missing_token")
    _require_token(len(token) <= 32768, "malformed_token")
    parts = token.split(".")
    _require_token(
        len(parts) == 3 and all(re.fullmatch(r"[A-Za-z0-9_-]+", p) for p in parts),
        "malformed_token",
    )
    head, body, signature = parts
    header = json_object(b64(head))
    claims = json_object(b64(body))
    _require_token(header.get("alg") == "RS256", "unsupported_algorithm")
    _require_token(
        not any(k in header for k in ("crit", "jku", "x5u", "b64")),
        "unsupported_header",
    )
    kid = header.get("kid")
    _require_token(isinstance(kid, str) and 1 <= len(kid) <= 200, "missing_key_id")
    _require_token(
        isinstance(jwks, dict)
        and isinstance(jwks.get("keys"), list)
        and len(jwks["keys"]) <= 50,
        "signing_key_unavailable",
    )
    keys = [
        k
        for k in jwks["keys"]
        if isinstance(k, dict)
        and k.get("kid") == kid
        and k.get("kty") == "RSA"
        and k.get("use", "sig") == "sig"
        and k.get("alg", "RS256") == "RS256"
    ]
    _require_token(len(keys) == 1, "signing_key_unavailable")
    key = keys[0]
    try:
        if "key_ops" in key:
            _require_token(
                isinstance(key["key_ops"], list) and "verify" in key["key_ops"],
                "invalid_signing_key",
            )
        n = int.from_bytes(b64(key["n"]), "big")
        e = int.from_bytes(b64(key["e"]), "big")
        _require_token(
            2048 <= n.bit_length() <= 8192 and 3 <= e <= 2**32 and e % 2 == 1,
            "invalid_signing_key",
        )
        public_key = rsa.RSAPublicNumbers(e, n).public_key()
    except (ValueError, TypeError, KeyError):
        raise _InvalidIDToken("invalid_signing_key") from None
    try:
        public_key.verify(
            b64(signature),
            (head + "." + body).encode("ascii"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
    except InvalidSignature:
        raise _InvalidIDToken("signature_mismatch") from None

    # Interpret identity/claims only after verifying the signature.
    _require_token(claims.get("iss") == ISSUER, "issuer_mismatch")
    aud = claims.get("aud")
    audiences = [aud] if isinstance(aud, str) else aud
    _require_token(
        isinstance(audiences, list)
        and bool(audiences)
        and all(isinstance(a, str) and bool(a) for a in audiences)
        and client_id in audiences,
        "audience_mismatch",
    )
    _require_token(
        (len(audiences) <= 1 or claims.get("azp") == client_id)
        and claims.get("azp") in (None, client_id),
        "authorized_party_mismatch",
    )
    exp = claims.get("exp")
    _require_token(
        type(exp) in (int, float) and math.isfinite(exp), "invalid_timestamp"
    )
    _require_token(exp > current - ID_TOKEN_CLOCK_SKEW_SECONDS, "token_expired")
    for field, reason in (("iat", "issued_in_future"), ("nbf", "not_yet_valid")):
        if field in claims:
            value = claims[field]
            _require_token(
                type(value) in (int, float) and math.isfinite(value),
                "invalid_timestamp",
            )
            _require_token(value <= current + ID_TOKEN_CLOCK_SKEW_SECONDS, reason)
    sub = claims.get("sub")
    _require_token(
        isinstance(sub, str)
        and 1 <= len(sub) <= 255
        and (subject is None or sub == subject),
        "subject_mismatch",
    )
    if nonce is not None:
        _require_token(isinstance(claims.get("nonce"), str), "nonce_missing")
        # compare_digest(str, str) raises on non-ASCII provider input. Comparing
        # UTF-8 bytes safely rejects that mismatch with a nonce diagnostic.
        _require_token(
            secrets.compare_digest(
                claims["nonce"].encode("utf-8"), nonce.encode("utf-8")
            ),
            "nonce_mismatch",
        )
    return {
        k: claims[k]
        for k in ("sub", "name", "email")
        if k in claims and isinstance(claims[k], str) and len(claims[k]) <= 320
    }


def validate_id_token(token, jwks, client_id, nonce=None, subject=None, clock=None):
    """Pinned RS256 verification; return only verified identity or static reason.

    Keep the public error code stable for reauthorization handling. No token,
    provider value or raw exception is copied into a diagnostic or its cause.
    """
    try:
        return _verified_id_token(
            token,
            jwks,
            client_id,
            nonce,
            subject,
            time.time() if clock is None else clock,
        )
    except _InvalidIDToken as error:
        reason = error.reason
    except Exception:
        reason = "malformed_token"
    error = GSCError("chatgpt_invalid_id_token", ID_TOKEN_REASONS[reason], 401)
    error.token_reason = reason
    raise error from None


def discovery_metadata(raw):
    if (
        raw.get("issuer") != ISSUER
        or raw.get("authorization_endpoint") != AUTHORIZE
        or raw.get("token_endpoint") != TOKEN
        or raw.get("jwks_uri") != JWKS
    ):
        fail(
            "chatgpt_discovery_invalid",
            "OIDC discovery không khớp endpoints OpenAI đã xác định.",
            502,
        )
    if (
        "code_challenge_methods_supported" in raw
        and "S256" not in raw["code_challenge_methods_supported"]
    ):
        fail("chatgpt_pkce_unsupported", "Issuer chưa công bố PKCE S256.", 502)
    if (
        "id_token_signing_alg_values_supported" in raw
        and "RS256" not in raw["id_token_signing_alg_values_supported"]
    ):
        fail(
            "chatgpt_signing_unsupported",
            "Issuer chưa công bố thuật toán ID token được adapter hỗ trợ.",
            502,
        )
    revoke = raw.get("revocation_endpoint")
    if revoke:
        p = urlsplit(revoke)
        if (
            p.scheme != "https"
            or p.netloc != "auth.openai.com"
            or not p.path
            or p.query
            or p.fragment
        ):
            fail(
                "chatgpt_discovery_invalid",
                "Revocation endpoint không thuộc issuer cố định.",
                502,
            )
    return raw


def provider_error(status):
    code, message = {
        400: (
            "chatgpt_request_rejected",
            "OpenAI từ chối request SIWC; kiểm tra quyền, model hoặc giới hạn preview.",
        ),
        401: (
            "chatgpt_reauthorization_required",
            "Phiên ChatGPT hết hạn hoặc bị thu hồi. Kết nối lại.",
        ),
        403: (
            "chatgpt_not_authorized",
            "Tài khoản hoặc ứng dụng chưa được OpenAI cho phép dùng ChatGPT Plan Usage.",
        ),
        429: (
            "chatgpt_quota",
            "ChatGPT đang giới hạn hạn mức/rate limit. Không chuyển sang API trả phí.",
        ),
        503: (
            "chatgpt_unavailable",
            "Dịch vụ hoặc kiểm tra hạn mức ChatGPT tạm thời không khả dụng.",
        ),
    }.get(
        status,
        (
            "chatgpt_provider_error",
            "OpenAI chưa hoàn tất request SIWC. Không tự retry hoặc chuyển provider.",
        ),
    )
    fail(code, message, status if status in (400, 401, 403, 429, 503) else 502)


def token_error(status, data):
    """Classify only known OAuth identifiers; never echo provider descriptions."""
    try:
        raw = json_object(data).get("error")
        code = raw.get("code") if isinstance(raw, dict) else raw
    except (ValueError, UnicodeError):
        code = None
    errors = {
        "invalid_grant": "chatgpt_oauth_invalid_grant",
        "invalid_client": "chatgpt_oauth_invalid_client",
        "unauthorized_client": "chatgpt_oauth_invalid_client",
        "invalid_request": "chatgpt_oauth_invalid_request",
        "unsupported_grant_type": "chatgpt_oauth_invalid_request",
        "invalid_scope": "chatgpt_oauth_invalid_scope",
        "invalid_target": "chatgpt_oauth_invalid_scope",
    }
    if status in (400, 401, 403) and isinstance(code, str) and code in errors:
        safe = errors[code]
        fail(safe, MESSAGES[safe], status)
    provider_error(status)


class ChatGPTTransport:
    def __init__(self, transport=None):
        self.transport = transport

    def client(self):
        return httpx.Client(
            transport=self.transport,
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(30, connect=8, write=10, pool=5),
        )

    def request(self, method, url, *, form=None, token=None):
        allowed = {DISCOVERY, JWKS, TOKEN, RESOURCE + "/models"}
        # Revocation is validated by OIDC discovery before calling this method.
        if url not in allowed and not (
            url.startswith(ISSUER + "/") and form and "token_type_hint" in form
        ):
            fail("chatgpt_endpoint", "Endpoint không được phép.", 403)
        try:
            with self.client() as client, client.stream(
                method,
                url,
                data=form,
                headers={"Authorization": "Bearer " + token} if token else {},
            ) as response:
                if response.status_code >= 300 and url != TOKEN:
                    provider_error(response.status_code)
                data = bytearray()
                deadline = time.monotonic() + 45
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data) > 512 * 1024 or time.monotonic() > deadline:
                        fail(
                            "chatgpt_response_limit",
                            "Phản hồi ChatGPT vượt giới hạn.",
                            502,
                        )
                if response.status_code >= 300:
                    token_error(response.status_code, data)
                if not data:
                    return {}
                try:
                    return json_object(data)
                except (ValueError, UnicodeError):
                    fail(
                        "chatgpt_invalid_response", "OpenAI trả JSON không hợp lệ.", 502
                    )
        except httpx.HTTPError:
            fail(
                "chatgpt_network",
                "Không kết nối được ChatGPT hoặc request hết thời gian. Không tự retry.",
                503,
            )

    def inference(self, token, payload, on_delta=None):
        """Allowlist differs deliberately from API-key requests; no unsupported caps."""
        if not isinstance(payload.get("input"), list):
            fail("chatgpt_input", "SIWC input cần là array.")
        body = {
            "model": payload["model"],
            "input": payload["input"],
            "store": False,
            "stream": True,
        }
        tools = payload.get("tools", [])
        if tools:
            if any(t.get("type") != "function" for t in tools):
                fail(
                    "chatgpt_hosted_tools",
                    "SIWC chỉ nhận function tools do LocalSEO quản lý.",
                    403,
                )
            body["tools"] = tools
        try:
            with self.client() as client, client.stream(
                "POST",
                RESOURCE + "/responses",
                json=body,
                headers={
                    "Authorization": "Bearer " + token,
                    "Accept": "text/event-stream",
                },
            ) as response:
                if response.status_code >= 300:
                    provider_error(response.status_code)
                if (
                    "text/event-stream"
                    not in response.headers.get("content-type", "").lower()
                ):
                    fail(
                        "chatgpt_not_sse", "SIWC chưa trả Responses event stream.", 502
                    )
                start = time.monotonic()
                buffer = b""
                total = 0
                for chunk in response.iter_bytes():
                    total += len(chunk)
                    buffer = (buffer + chunk).replace(b"\r\n", b"\n")
                    if (
                        total > MAX_BYTES
                        or len(buffer) > 512 * 1024
                        or time.monotonic() - start > 120
                    ):
                        fail(
                            "chatgpt_stream_limit",
                            "Stream vượt giới hạn kích thước/thời gian; hạn mức có thể đã được sử dụng.",
                            502,
                        )
                    while b"\n\n" in buffer:
                        block, buffer = buffer.split(b"\n\n", 1)
                        data = b"\n".join(
                            line[5:].lstrip(b" ")
                            for line in block.split(b"\n")
                            if line.startswith(b"data:")
                        )
                        if not data or data == b"[DONE]":
                            continue
                        try:
                            event = json_object(data)
                        except (ValueError, UnicodeError):
                            fail(
                                "chatgpt_invalid_sse", "Sự kiện SIWC không hợp lệ.", 502
                            )
                        typ = event.get("type")
                        if typ == "response.output_text.delta":
                            delta = event.get("delta")
                            if not isinstance(delta, str):
                                fail(
                                    "chatgpt_invalid_sse",
                                    "Text delta không hợp lệ.",
                                    502,
                                )
                            if on_delta:
                                on_delta(delta)
                        elif typ == "response.completed":
                            result = event.get("response")
                            if (
                                not isinstance(result, dict)
                                or result.get("status") != "completed"
                            ):
                                fail(
                                    "chatgpt_incomplete",
                                    "Terminal response chưa hoàn tất.",
                                    502,
                                )
                            return result
                        elif typ in ("response.failed", "response.incomplete", "error"):
                            if event.get("response") is not None and not isinstance(
                                event["response"], dict
                            ):
                                fail(
                                    "chatgpt_invalid_sse",
                                    "Error response trong stream không hợp lệ.",
                                    502,
                                )
                            error = (
                                event.get("error")
                                or (event.get("response") or {}).get("error")
                                or {}
                            )
                            code = (
                                error.get("code") if isinstance(error, dict) else None
                            )
                            status = (
                                error.get("status") or error.get("status_code")
                                if isinstance(error, dict)
                                else None
                            )
                            if status in (401, 403, 429, 503):
                                provider_error(status)
                            if code in (
                                "rate_limit_exceeded",
                                "insufficient_quota",
                                "usage_limit_reached",
                                "usage_limit_exceeded",
                                "quota_exceeded",
                            ):
                                provider_error(429)
                            if code in ("invalid_token", "token_expired"):
                                provider_error(401)
                            if code in ("permission_denied", "insufficient_scope"):
                                provider_error(403)
                            if code in (
                                "service_unavailable",
                                "temporarily_unavailable",
                            ):
                                provider_error(503)
                            fail(
                                "chatgpt_incomplete",
                                "ChatGPT báo failed/incomplete trong stream. Không coi text delta là kết quả thành công.",
                                502,
                            )
                fail(
                    "chatgpt_stream_interrupted",
                    "Stream kết thúc trước response.completed; chưa xác nhận thành công. Không tự gửi lại hoặc chuyển API trả phí.",
                    502,
                )
        except httpx.HTTPError:
            fail(
                "chatgpt_stream_interrupted",
                "Stream ChatGPT mất kết nối hoặc hết thời gian; không tự retry. Hạn mức có thể đã được sử dụng.",
                503,
            )
