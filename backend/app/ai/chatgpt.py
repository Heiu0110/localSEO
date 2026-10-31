"""Single-user SIWC dynamic registration, loopback callback and rotating OS-vault tokens."""

import base64
import hashlib
import json
import re
import secrets
import threading
import time
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from uuid import uuid4
from sqlalchemy import select
from app.db.models import Setting
from app.gsc.errors import GSCError
from .common import fail, now
from .chatgpt_protocol import *
from .chatgpt_diagnostics import OAUTH_DIAGNOSTIC, STAGES, diagnostic

TOKENS = "ai.chatgpt.tokens.v1"
REGISTRATION = "ai.chatgpt.registration.v1"
HOST = "ai.chatgpt.host_id"
MODEL = "ai.chatgpt.model.v1"
MODELS = "ai.chatgpt.models.v1"
CLIENT_PATTERN = re.compile(r"^oaiapp_[A-Za-z0-9_-]{1,200}$")
DOCS = [
    "https://developers.openai.com/siwc/quickstart",
    "https://developers.openai.com/siwc/token-sharing-open-source",
    "https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference",
    "https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations",
]


def scopes(value):
    if not isinstance(value, str) or len(value) > 4000:
        fail("chatgpt_invalid_scope", "OpenAI chưa trả granted scope hợp lệ.", 502)
    return sorted(set(value.split()))


def issued_client(value):
    if not isinstance(value, str) or not CLIENT_PATTERN.fullmatch(value):
        fail(
            "chatgpt_invalid_client",
            "Callback chưa có issued client ID oaiapp_ hợp lệ; không dùng dynamic_agent_client khi exchange.",
            400,
        )
    return value


class LoopbackServer(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def get_request(self):
        sock, addr = super().get_request()
        sock.settimeout(5)
        return sock, addr


class ChatGPTConnection:
    def __init__(self, db, vault, transport=None, clock=None):
        self.db = db
        self.vault = vault
        self.http = ChatGPTTransport(transport)
        self.clock = clock or time.time
        self.lock = threading.RLock()
        self.pending = None
        self.server = None
        self.timer = None
        self.phase = "idle"
        self.last_error = None
        self.metadata = None
        self.metadata_at = 0
        self.active_inferences = 0

    def _get(self, key, default=None):
        with self.db.session() as s:
            obj = s.get(Setting, key)
            return json.loads(obj.value) if obj else default

    def _put(self, key, value):
        with self.db.session.begin() as s:
            s.merge(Setting(key=key, value=json.dumps(value)))

    def _record_oauth_error(self, code, stage, reason=None):
        self.last_error = diagnostic(code, stage, reason)
        try:
            # Only static identifiers survive a backend restart, never query
            # parameters, provider response bodies, account data or tokens.
            self._put(
                OAUTH_DIAGNOSTIC,
                {
                    k: self.last_error[k]
                    for k in ("code", "stage", "reason")
                    if k in self.last_error
                },
            )
        except Exception:
            pass  # Keep the original diagnostic if SQLite is itself unavailable.

    def _clear_models(self):
        self._put(MODELS, {"session_id": None, "models": [], "fetched_at": 0})
        self._put(MODEL, {"session_id": None, "slug": None})

    def _host(self):
        # A SQLite backup copied to another machine must not clone the host identity.
        value = self.vault.get(HOST) or {}
        if not value.get("id"):
            value = {"id": "urn:uuid:" + str(uuid4())}
            self.vault.put(HOST, value)
        return value["id"]

    def _oidc(self, force=False):
        if force or not self.metadata or self.clock() - self.metadata_at > 3600:
            self.metadata = discovery_metadata(self.http.request("GET", DISCOVERY))
            self.metadata_at = self.clock()
        return self.metadata

    def _validate(self, token, client, nonce=None, subject=None):
        self._oidc()
        keys = self.http.request("GET", JWKS)
        if not isinstance(keys.get("keys"), list) or len(keys["keys"]) > 50:
            fail("chatgpt_jwks", "JWKS không hợp lệ.", 502)
        return validate_id_token(token, keys, client, nonce, subject, self.clock())

    def _stop_listener(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None
        server = self.server
        self.server = None
        if server:
            server.shutdown()
            server.server_close()

    def _expire(self, state):
        with self.lock:
            if self.pending and secrets.compare_digest(self.pending["state"], state):
                self.pending = None
                self.phase = "failed"
                self._record_oauth_error("chatgpt_oauth_expired", "callback_validation")
                self._stop_listener()

    def close(self):
        with self.lock:
            if self.pending:
                self._record_oauth_error("chatgpt_oauth_interrupted", "callback_validation")
                self.phase = "failed"
            self.pending = None
            self._stop_listener()

    def status(self):
        with self.lock:
            last_error = self.last_error
            if not last_error and self.phase == "idle":
                saved = self._get(OAUTH_DIAGNOSTIC, {})
                if isinstance(saved, dict) and saved.get("code"):
                    last_error = diagnostic(
                        saved.get("code"), saved.get("stage"), saved.get("reason")
                    )
            secure = True
            try:
                raw = self.vault.get(TOKENS) or {}
            except GSCError:
                secure = False
                raw = {}
            state = "not_connected"
            if raw:
                state = (
                    "reauthorization_required"
                    if raw.get("reauthorization_required")
                    else (
                        "connected_authorized"
                        if DIRECT in raw.get("scopes", [])
                        else "connected_not_authorized"
                    )
                )
                if (
                    state == "connected_authorized"
                    and raw.get("expires_at", 0) <= self.clock()
                ):
                    state = (
                        "token_expired_refresh_available"
                        if raw.get("refresh_token")
                        and raw.get("refresh_expires_at", 0) > self.clock()
                        else "reauthorization_required"
                    )
            cached = self._get(MODELS, {})
            models = (
                cached.get("models", [])
                if raw and cached.get("session_id") == raw.get("session_id")
                else []
            )
            selected = self._get(MODEL, {})
            model = (
                selected.get("slug")
                if raw and selected.get("session_id") == raw.get("session_id")
                else None
            )
            root = Path(__file__).resolve().parents[3]
            license_found = any(
                (root / name).is_file()
                for name in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
            )
            return {
                "provider": "chatgpt",
                "status": state,
                "secure_storage_available": secure,
                "authorization_status": "failed" if self.phase == "idle" and last_error else self.phase,
                "pending_authorization": self.phase in ("waiting", "exchanging"),
                "account": raw.get("account") if raw else None,
                "connection_id": raw.get("session_id"),
                "granted_scopes": raw.get("scopes", []),
                "plan_usage_authorized": state
                in ("connected_authorized", "token_expired_refresh_available")
                and DIRECT in raw.get("scopes", []),
                "access_expires_at": raw.get("expires_at"),
                "refresh_expires_at": raw.get("refresh_expires_at"),
                "models": models,
                "selected_model": model,
                "models_stale": self.clock() - cached.get("fetched_at", 0) > 300,
                "last_error": last_error,
                "eligibility": {
                    "status": "pending_live_verification",
                    "repository_license_found": license_found,
                    "user_review_required": True,
                    "note": "Chưa xác nhận LocalSEO/tài khoản đủ điều kiện preview. Checkbox xác nhận review không cấp giấy phép mã nguồn hoặc bảo đảm eligibility.",
                },
                "live_verification": (
                    "verified_for_this_session"
                    if raw.get("inference_verified_at")
                    else "pending_live_verification"
                ),
                "inference_verified_at": raw.get("inference_verified_at"),
                "quota": {
                    "status": "unknown",
                    "remaining": None,
                    "note": "Scope cho phép không chứng minh còn hạn mức hoặc tài khoản thuộc gói Plus; OpenAI quyết định khi inference.",
                },
                "protocol_source": "user_supplied_official_handoff_2026_10_29",
                "full_preview_limitations_verified": False,
                "documentation": DOCS,
                "fallback_to_api_key": False,
            }

    def start(self, eligibility_acknowledged, localhost_acknowledged):
        if not eligibility_acknowledged or not localhost_acknowledged:
            fail(
                "chatgpt_eligibility_review",
                "Cần xác nhận đã rà soát điều kiện OSS/locally hosted và đang chạy trình duyệt cùng máy localhost.",
                409,
            )
        with self.lock:
            if self.active_inferences:
                fail(
                    "chatgpt_busy",
                    "Chờ inference ChatGPT hiện tại hoàn tất trước khi đổi kết nối.",
                    409,
                )
            registration = (
                self.vault.get(REGISTRATION) or {}
            )  # Validates OS vault before opening any listener/browser.
            client = (
                issued_client(registration["client_id"])
                if registration.get("client_id")
                else "dynamic_agent_client"
            )
            self._oidc()
            self._stop_listener()
            self.last_error = None
            self._put(OAUTH_DIAGNOSTIC, {})
            owner = self

            class Callback(BaseHTTPRequestHandler):
                def log_message(self, *args):
                    pass

                def send_error(self, code, message=None, explain=None):
                    self.send_response(code)
                    self.send_header("Content-Type", "text/plain; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    self.wfile.write(b"Invalid OAuth callback request.")

                def do_GET(self):
                    status = 400
                    success = False
                    failure = diagnostic("chatgpt_callback")
                    try:
                        if (
                            len(self.path) > 16384
                            or self.headers.get("Host")
                            != f"127.0.0.1:{self.server.server_port}"
                        ):
                            fail(
                                "chatgpt_callback_host",
                                "Callback host không hợp lệ.",
                                400,
                            )
                        parsed = urlsplit(self.path)
                        if (
                            parsed.scheme
                            or parsed.netloc
                            or len(self.headers.get_all("Host", [])) != 1
                        ):
                            fail(
                                "chatgpt_callback_host",
                                "Callback target không hợp lệ.",
                                400,
                            )
                        if parsed.path != "/auth/callback":
                            fail(
                                "chatgpt_callback_path",
                                "Callback path không hợp lệ.",
                                404,
                            )
                        query = parse_qs(
                            parsed.query, keep_blank_values=True, max_num_fields=12
                        )
                        if any(len(v) != 1 for v in query.values()):
                            fail("chatgpt_callback", "Query callback bị trùng.", 400)
                        owner.callback({k: v[0] for k, v in query.items()})
                        success = True
                        status = 200
                    except GSCError as error:
                        status = error.status
                        failure = diagnostic(
                            error.code,
                            getattr(error, "oauth_stage", "callback_validation"),
                            getattr(error, "token_reason", None),
                        )
                    except Exception:
                        status = 400
                    nonce = secrets.token_urlsafe(24)
                    self.send_response(status)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header(
                        "Content-Security-Policy",
                        f"default-src 'none'; script-src 'nonce-{nonce}'; style-src 'nonce-{nonce}'; frame-ancestors 'none'; base-uri 'none'",
                    )
                    self.send_header("Referrer-Policy", "no-referrer")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    self.wfile.write(
                        (
                            '<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LocalSEO · ChatGPT</title>'
                            + f'<script nonce="{nonce}">try{{history.replaceState(null,"","/auth/callback")}}catch{{}}</script>'
                            + f'<style nonce="{nonce}">body{{font:16px/1.7 system-ui,sans-serif;margin:48px auto;padding:24px;max-width:680px;background:#f0f0ef;color:#171717}}main{{background:#fff;padding:32px;border-radius:24px}}h1{{font-size:24px}}code{{overflow-wrap:anywhere}}p{{margin:16px 0}}</style><main><h1>'
                            + (
                                "Đã hoàn tất đăng nhập. Quay lại AI Settings của LocalSEO."
                                if success
                                else "Chưa hoàn tất đăng nhập. Quay lại AI Settings để xem trạng thái và thử lại."
                            )
                            + "</h1>"
                            + (
                                ""
                                if success
                                else "<p><strong>Mã lỗi:</strong> <code>"
                                + escape(failure["code"])
                                + "</code><br><strong>Bước:</strong> "
                                + escape(STAGES[failure["stage"]])
                                + "</p>"
                                + (
                                    "<p><strong>Chi tiết kiểm tra:</strong> <code>"
                                    + escape(failure["reason"])
                                    + "</code></p>"
                                    if failure.get("reason")
                                    else ""
                                )
                                + "<p>"
                                + escape(failure["detail"])
                                + "</p>"
                            )
                            + "<p>Quay lại tab LocalSEO → AI Workspace → AI Settings → ChatGPT Connection. Nhấn <strong>Làm mới trạng thái ChatGPT</strong> để kiểm tra; nếu thất bại, bắt đầu lại bằng <strong>Continue with ChatGPT</strong>.</p><p>Không tải lại callback cũ hoặc chia sẻ URL đăng nhập, code hay token.</p></main></html>"
                        ).encode()
                    )
                    if owner.phase not in ("waiting", "exchanging"):
                        threading.Thread(
                            target=owner._close_finished_listener, daemon=True
                        ).start()

            host_id = self._host()
            self.server = LoopbackServer(("127.0.0.1", 0), Callback)
            redirect = f"http://127.0.0.1:{self.server.server_port}/auth/callback"
            verifier = secrets.token_urlsafe(48)
            state = secrets.token_urlsafe(32)
            nonce = secrets.token_urlsafe(32)
            self.pending = {
                "state": state,
                "nonce": nonce,
                "verifier": verifier,
                "redirect_uri": redirect,
                "client_id": client,
                "expires_at": self.clock() + 600,
            }
            self.phase = "waiting"
            threading.Thread(
                target=self.server.serve_forever,
                kwargs={"poll_interval": 0.1},
                daemon=True,
                name="chatgpt-loopback",
            ).start()
            self.timer = threading.Timer(600, self._expire, args=(state,))
            self.timer.daemon = True
            self.timer.start()
            params = {
                "client_id": client,
                "agent_name_hint": "LocalSEO",
                "ext_agent_host_id": host_id,
                "response_type": "code",
                "scope": SCOPES,
                "resource": RESOURCE,
                "code_challenge_method": "S256",
                "code_challenge": base64.urlsafe_b64encode(
                    hashlib.sha256(verifier.encode()).digest()
                )
                .rstrip(b"=")
                .decode(),
                "state": state,
                "nonce": nonce,
                "redirect_uri": redirect,
            }
            return {
                "authorization_url": AUTHORIZE + "?" + urlencode(params),
                "redirect_uri": redirect,
                "expires_in": 600,
                "dynamic_registration": client == "dynamic_agent_client",
                "eligibility": "pending_live_verification",
            }

    def _close_finished_listener(self):
        with self.lock:
            if not self.pending and self.phase not in ("waiting", "exchanging"):
                self._stop_listener()

    def callback(self, query):
        with self.lock:
            stage = "callback_validation"
            pending = self.pending
            if (
                not pending
                or not isinstance(query.get("state"), str)
                or not secrets.compare_digest(pending["state"], query["state"])
            ):
                fail(
                    "chatgpt_invalid_state",
                    "State callback không hợp lệ hoặc đã sử dụng.",
                    400,
                )
            self.pending = None
            self.phase = "exchanging"
            try:
                if pending["expires_at"] <= self.clock():
                    fail(
                        "chatgpt_oauth_expired",
                        "Phiên OAuth hết hạn. Bắt đầu lại.",
                        400,
                    )
                if query.get("error"):
                    fail(
                        "chatgpt_consent_denied",
                        "Người dùng hoặc OpenAI chưa cấp quyền đăng nhập.",
                        400,
                    )
                code = query.get("code")
                if not isinstance(code, str) or not 1 <= len(code) <= 4096:
                    fail(
                        "chatgpt_callback_code",
                        "Callback chưa có authorization code hợp lệ.",
                        400,
                    )
                stage = "client_registration"
                client = issued_client(
                    query.get("client_id")
                    or (
                        pending["client_id"]
                        if pending["client_id"] != "dynamic_agent_client"
                        else None
                    )
                )
                if (
                    pending["client_id"] != "dynamic_agent_client"
                    and client != pending["client_id"]
                ):
                    fail(
                        "chatgpt_client_changed",
                        "Client ID không khớp phiên đăng nhập.",
                        400,
                    )
                stage = "token_exchange"
                result = self.http.request(
                    "POST",
                    TOKEN,
                    form={
                        "grant_type": "authorization_code",
                        "client_id": client,
                        "code": code,
                        "code_verifier": pending["verifier"],
                        "redirect_uri": pending["redirect_uri"],
                        "resource": RESOURCE,
                    },
                )
                stage = "id_token_validation"
                account = self._validate(
                    result.get("id_token"), client, pending["nonce"]
                )
                value = self._credentials(result, client, account)
                stage = "credential_storage"
                self.vault.put(
                    REGISTRATION, {"client_id": client, "sub": account["sub"]}
                )
                self.vault.put(TOKENS, value)
                stage = "model_listing"
                self._clear_models()
                self.phase = "completed"
                self.last_error = None
                self._put(OAUTH_DIAGNOSTIC, {})
                if DIRECT in value["scopes"]:
                    try:
                        self._refresh_models_locked()
                    except GSCError as error:
                        self.last_error = {"code": error.code, "detail": error.message}
                        self.last_error["stage"] = "model_listing"
            except GSCError as error:
                self.phase = "failed"
                error.oauth_stage = stage
                self._record_oauth_error(
                    error.code, stage, getattr(error, "token_reason", None)
                )
                raise
            except Exception:
                self.phase = "failed"
                self._record_oauth_error("chatgpt_oauth_failed", stage)
                error = GSCError("chatgpt_oauth_failed", self.last_error["detail"], 502)
                error.oauth_stage = stage
                raise error from None

    def _credentials(self, result, client, account, previous=None):
        access = result.get("access_token")
        refresh = result.get("refresh_token")
        expires = result.get("expires_in")
        if (
            not isinstance(result.get("token_type"), str)
            or result.get("token_type", "").casefold() != "bearer"
            or not isinstance(access, str)
            or not 1 <= len(access) <= 16000
            or not isinstance(refresh, str)
            or not 1 <= len(refresh) <= 16000
            or any(ord(c) < 33 or ord(c) == 127 for c in access + refresh)
            or type(expires) not in (int, float)
            or not math.isfinite(expires)
            or not 0 < expires <= 86400
        ):
            fail(
                "chatgpt_invalid_tokens",
                "Token response thiếu Bearer token, refresh rotation hoặc thời hạn hợp lệ.",
                502,
            )
        granted = scopes(
            result.get("scope")
            if "scope" in result
            else " ".join(previous["scopes"]) if previous else ""
        )
        return {
            "client_id": client,
            "account": account,
            "access_token": access,
            "refresh_token": refresh,
            "scopes": granted,
            "expires_at": self.clock() + expires,
            "refresh_expires_at": self.clock() + 30 * 86400,
            "session_id": previous["session_id"] if previous else uuid4().hex,
            "reauthorization_required": False,
            "inference_verified_at": (
                previous.get("inference_verified_at") if previous else None
            ),
        }

    def _invalidate(self, raw):
        self.vault.put(
            TOKENS,
            {
                **raw,
                "access_token": "",
                "refresh_token": "",
                "reauthorization_required": True,
            },
        )
        self._clear_models()

    def credentials(self, expected_session=None):
        with self.lock:
            raw = self.vault.get(TOKENS)
            if not raw or raw.get("reauthorization_required"):
                fail(
                    "chatgpt_not_connected",
                    "Kết nối lại ChatGPT trong AI Settings.",
                    401,
                )
            if expected_session and raw["session_id"] != expected_session:
                fail(
                    "chatgpt_account_changed",
                    "Kết nối ChatGPT đã đổi; kiểm tra và xác nhận lượt mới.",
                    409,
                )
            if DIRECT not in raw.get("scopes", []):
                fail(
                    "chatgpt_plan_not_authorized",
                    "Connected — ChatGPT Plan Usage Not Authorized. Chưa có quyền chatgpt.tokens.use.direct.",
                    403,
                )
            if raw["expires_at"] <= self.clock() + 60:
                if raw.get("refresh_expires_at", 0) <= self.clock() or not raw.get(
                    "refresh_token"
                ):
                    self._invalidate(raw)
                    fail(
                        "chatgpt_refresh_expired",
                        "Refresh token hết hạn. Kết nối lại ChatGPT.",
                        401,
                    )
                try:
                    result = self.http.request(
                        "POST",
                        TOKEN,
                        form={
                            "grant_type": "refresh_token",
                            "client_id": raw["client_id"],
                            "refresh_token": raw["refresh_token"],
                            "resource": RESOURCE,
                        },
                    )
                    account = (
                        self._validate(
                            result["id_token"],
                            raw["client_id"],
                            subject=raw["account"]["sub"],
                        )
                        if result.get("id_token")
                        else raw["account"]
                    )
                    updated = self._credentials(result, raw["client_id"], account, raw)
                    self.vault.put(TOKENS, updated)
                    raw = updated
                except GSCError as error:
                    if error.code in (
                        "chatgpt_request_rejected",
                        "chatgpt_reauthorization_required",
                        "chatgpt_invalid_id_token",
                        "chatgpt_oauth_invalid_grant",
                        "chatgpt_oauth_invalid_client",
                    ):
                        self._invalidate(raw)
                        fail(
                            "chatgpt_reauthorization_required",
                            "Refresh token không còn hợp lệ hoặc bị thu hồi. Kết nối lại ChatGPT.",
                            401,
                        )
                    raise
                if DIRECT not in raw["scopes"]:
                    self._clear_models()
                    fail(
                        "chatgpt_plan_not_authorized",
                        "Quyền ChatGPT Plan Usage không còn trong granted scopes.",
                        403,
                    )
            return raw

    def _refresh_models_locked(self):
        raw = self.credentials()
        try:
            result = self.http.request(
                "GET", RESOURCE + "/models", token=raw["access_token"]
            )
        except GSCError as error:
            if error.status == 401:
                self._invalidate(raw)
            raise
        entries = result.get("models")
        if not isinstance(entries, list) or len(entries) > 1000:
            fail(
                "chatgpt_models_invalid",
                "OpenAI chưa trả danh sách models hợp lệ theo SIWC.",
                502,
            )
        models = []
        seen = set()
        for item in entries:
            if not isinstance(item, dict) or item.get("visibility") != "list":
                continue
            slug = item.get("slug")
            label = item.get("display_name")
            if (
                not isinstance(slug, str)
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,149}", slug)
                or slug in seen
                or not isinstance(label, str)
                or not 1 <= len(label) <= 200
            ):
                fail(
                    "chatgpt_models_invalid",
                    "Model listing có slug/display_name không hợp lệ.",
                    502,
                )
            models.append({"slug": slug, "display_name": label})
            seen.add(slug)
        self._put(
            MODELS,
            {
                "session_id": raw["session_id"],
                "models": models,
                "fetched_at": self.clock(),
            },
        )
        return models

    def refresh_models(self):
        with self.lock:
            self._refresh_models_locked()
            return self.status()

    def select_model(self, slug):
        with self.lock:
            self.credentials()
            self._refresh_models_locked()
            cached = self._get(MODELS)
            if slug not in {m["slug"] for m in cached["models"]}:
                fail(
                    "chatgpt_model_unavailable",
                    "Model không nằm trong danh sách visibility=list của tài khoản.",
                    409,
                )
            self._put(MODEL, {"session_id": cached["session_id"], "slug": slug})
            return self.status()

    def preflight(self):
        with self.lock:
            raw = self.credentials()
            cached = self._get(MODELS, {})
            if (
                cached.get("session_id") != raw["session_id"]
                or self.clock() - cached.get("fetched_at", 0) > 300
            ):
                self._refresh_models_locked()
                cached = self._get(MODELS, {})
            selected = self._get(MODEL, {})
            if selected.get("session_id") != raw["session_id"] or selected.get(
                "slug"
            ) not in {m["slug"] for m in cached.get("models", [])}:
                fail(
                    "chatgpt_model_unavailable",
                    "Chọn model ChatGPT khả dụng trong AI Settings trước khi gửi.",
                    409,
                )
            return {
                "provider": "chatgpt",
                "model": selected["slug"],
                "connection_id": raw["session_id"],
                "requires_external_consent": True,
                "billing_source": "chatgpt_plan",
                "quota_remaining": None,
                "estimated_cost_usd": None,
                "fallback_to_api_key": False,
                "live_verification": (
                    "pending_live_verification"
                    if not raw.get("inference_verified_at")
                    else "verified_for_this_session"
                ),
            }

    def respond(self, payload, expected_session, on_delta=None):
        with self.lock:
            flight = self.preflight()
            if (
                flight["connection_id"] != expected_session
                or flight["model"] != payload["model"]
            ):
                fail(
                    "chatgpt_connection_changed",
                    "Tài khoản/model ChatGPT đã đổi; cần xác nhận lại.",
                    409,
                )
            raw = self.credentials(expected_session)
            self.active_inferences += 1
        try:
            result = self.http.inference(raw["access_token"], payload, on_delta)
            self.last_error = None
            with self.lock:
                latest = self.vault.get(TOKENS)
                if latest and latest["session_id"] == expected_session:
                    self.vault.put(TOKENS, {**latest, "inference_verified_at": now()})
            return result
        except GSCError as error:
            with self.lock:
                latest = self.vault.get(TOKENS)
                if latest and latest["session_id"] == expected_session:
                    self.last_error = {"code": error.code, "detail": error.message}
                    if error.status == 401:
                        self._invalidate(latest)
            raise
        finally:
            with self.lock:
                self.active_inferences -= 1

    def disconnect(self, revoke=True):
        with self.lock:
            self.pending = None
            self._stop_listener()
            self.phase = "idle"
            self.last_error = None
            try:
                raw = self.vault.get(TOKENS)
            except GSCError:
                raw = None  # A corrupt chunk must not prevent explicit Disconnect.
            revoked = False
            try:
                endpoint = (
                    self._oidc().get("revocation_endpoint") if revoke and raw else None
                )
                if endpoint:
                    for kind in ("refresh_token", "access_token"):
                        if raw.get(kind):
                            self.http.request(
                                "POST",
                                endpoint,
                                form={
                                    "client_id": raw["client_id"],
                                    "token": raw[kind],
                                    "token_type_hint": kind,
                                },
                            )
                    revoked = True
            except GSCError:
                pass
            finally:
                self.vault.delete(TOKENS)
                self._clear_models()
                self._put(OAUTH_DIAGNOSTIC, {})
            return {
                "local_credentials_removed": True,
                "remote_revoked": revoked,
                "registration_retained": True,
                "message": "Đã xóa token cục bộ. "
                + (
                    "OpenAI đã nhận yêu cầu revocation."
                    if revoked
                    else "Chưa xác nhận thu hồi từ xa; kiểm tra quyền trong tài khoản ChatGPT nếu cần."
                ),
            }
