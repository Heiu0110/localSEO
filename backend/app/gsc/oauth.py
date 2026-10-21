import json
import secrets
import threading
import time
from dataclasses import dataclass
from uuid import uuid4

import httpx
from google.auth.exceptions import RefreshError, TransportError
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from sqlalchemy import select

from app.db.models import Connection, Setting
from app.gsc.dates import bounds, now
from app.gsc.errors import GSCError
from app.gsc.schemas import DisconnectResult, IntegrationStatus

SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
CALLBACK = "http://127.0.0.1:8000/api/integrations/gsc/oauth/callback"


class TimedGoogleRequest(GoogleRequest):
    def __call__(self, *args, **kwargs):
        kwargs["timeout"] = 30
        return super().__call__(*args, **kwargs)


@dataclass
class Authorization:
    flow: Flow
    state: str
    expires: float
    connection_id: str


class OAuthService:
    def __init__(self, db, vault):
        self.db, self.vault = db, vault
        self.pending: Authorization | None = None
        self.lock = threading.RLock()
        self.last_error: str | None = None

    def connection_id(self) -> str | None:
        with self.db.session() as session:
            setting = session.get(Setting, "active_google_connection")
            return setting.value if setting else None

    def status(self) -> IntegrationStatus:
        first, final = bounds()
        configured, secure, message = False, True, None
        try:
            configured = self.vault.get("oauth-client") is not None
        except GSCError as exc:
            secure, message = False, exc.message
        connection_id = self.connection_id()
        with self.db.session() as session:
            connection = session.get(Connection, connection_id) if connection_id else None
            state = connection.status if connection and connection.status == "connected" else "connection_error" if self.last_error else connection.status if connection else "ready" if configured else "not_configured"
            return IntegrationStatus(status=state, configured=configured, secure_storage_available=secure,
                                     connection_id=connection_id, display_name=connection.display_name if connection else None,
                                     scope=SCOPE, latest_final_date=final, history_start=first, message=self.last_error or message,
                                     pending_authorization=bool(self.pending and self.pending.expires > time.monotonic()))

    def configure(self, content: bytes):
        if len(content) > 64 * 1024:
            raise GSCError("invalid_credentials_file", "Tệp OAuth JSON vượt quá 64 KB.")
        try:
            data = json.loads(content)
            installed = data["installed"]
            if (not isinstance(installed, dict) or not installed["client_id"].endswith(".apps.googleusercontent.com")
                or not isinstance(installed["client_secret"], str) or not installed["client_secret"]
                or installed["token_uri"] != "https://oauth2.googleapis.com/token"
                or installed["auth_uri"] not in ("https://accounts.google.com/o/oauth2/auth", "https://accounts.google.com/o/oauth2/v2/auth")):
                raise ValueError("Invalid Desktop client")
        except (KeyError, TypeError, ValueError, AttributeError):
            raise GSCError("invalid_credentials_file", "Hãy chọn credentials JSON của OAuth Desktop app do Google cấp, với endpoint Google hợp lệ.") from None
        with self.lock:
            state = self.status()
            if state.status == "connected":
                raise GSCError("disconnect_first", "Ngắt kết nối hiện tại trước khi thay OAuth client.", 409)
            self.vault.put("oauth-client", {"installed": installed})
            self.pending = None
            self.last_error = None

    def start(self) -> dict:
        with self.lock:
            config = self.vault.get("oauth-client")
            if not config:
                raise GSCError("not_configured", "Hãy nhập tệp OAuth Desktop JSON trước.", 409)
            flow = Flow.from_client_config(config, scopes=[SCOPE], redirect_uri=CALLBACK, autogenerate_code_verifier=True)
            # Consent only on an explicit connection action, never at application startup.
            url, state = flow.authorization_url(access_type="offline", prompt="consent")
            self.pending = Authorization(flow, state, time.monotonic() + 600, self.connection_id() or str(uuid4()))
            self.last_error = None
            return {"authorization_url": url, "expires_in": 600}

    def callback(self, state: str, code: str | None, error: str | None):
        with self.lock:
            pending = self.pending
            if not pending or pending.expires <= time.monotonic() or not secrets.compare_digest(pending.state, state):
                raise GSCError("invalid_oauth_state", "Phiên xác thực không hợp lệ hoặc đã hết hạn. Hãy kết nối lại.", 400)
            self.pending = None  # One-time state, including denied callbacks.
            if error or not code:
                self.last_error = "Google chưa cấp quyền. Bạn có thể quay lại Cài đặt và kết nối lại."
                raise GSCError("authorization_denied", self.last_error)
            try:
                pending.flow.fetch_token(code=code, timeout=30)
                credentials = pending.flow.credentials
                if not credentials.refresh_token:
                    raise GSCError("missing_refresh_token", "Google chưa cấp quyền ngoại tuyến. Hãy thu hồi quyền cũ trong tài khoản Google rồi kết nối lại.")
                self.vault.put(f"tokens:{pending.connection_id}", json.loads(credentials.to_json()))
            except GSCError as exc:
                self.last_error = exc.message
                raise
            except Exception:
                self.last_error = "Không thể hoàn tất xác thực Google. Kiểm tra Internet, OAuth client và kết nối lại."
                raise GSCError("oauth_exchange_failed", self.last_error, 502) from None
            stamp = now()
            with self.db.session.begin() as session:
                connection = session.get(Connection, pending.connection_id)
                if not connection:
                    connection = Connection(id=pending.connection_id, display_name="Google Search Console", provider="google", created_at=stamp,
                                            status="connected", scope=SCOPE, updated_at=stamp)
                    session.add(connection)
                connection.status, connection.updated_at = "connected", stamp
                session.merge(Setting(key="active_google_connection", value=connection.id))

    def mark_reauthorization(self, connection_id: str):
        with self.db.session.begin() as session:
            connection = session.get(Connection, connection_id)
            if connection:
                connection.status, connection.updated_at = "reauthorization_required", now()

    def credentials(self, connection_id: str) -> Credentials:
        with self.lock:
            return self._credentials(connection_id)

    def _credentials(self, connection_id: str) -> Credentials:
        raw = self.vault.get(f"tokens:{connection_id}")
        if not raw:
            self.mark_reauthorization(connection_id)
            raise GSCError("reauthorization_required", "Phiên Google không còn khả dụng. Hãy kết nối lại trong Cài đặt.", 401)
        credentials = Credentials.from_authorized_user_info(raw, scopes=[SCOPE])
        if not credentials.valid:
            try:
                credentials.refresh(TimedGoogleRequest())
                self.save_credentials(connection_id, credentials)
            except RefreshError:
                self.mark_reauthorization(connection_id)
                raise GSCError("reauthorization_required", "Quyền Google đã hết hạn hoặc bị thu hồi. Hãy kết nối lại.", 401) from None
            except TransportError:
                raise GSCError("offline", "Không thể kết nối Google để làm mới phiên. Dữ liệu SQLite vẫn có thể đọc ngoại tuyến.", 503, True) from None
        return credentials

    def save_credentials(self, connection_id: str, credentials: Credentials):
        with self.lock:
            with self.db.session() as session:
                connection = session.get(Connection, connection_id)
                if connection and connection.status == "disconnected":
                    raise GSCError("connection_changed", "Kết nối Google đã bị ngắt. Hãy kết nối lại trước khi truy xuất.", 401)
            self.vault.put(f"tokens:{connection_id}", json.loads(credentials.to_json()))

    def disconnect(self, revoke: bool) -> DisconnectResult:
        with self.lock:
            connection_id = self.connection_id()
            self.pending = None
            self.last_error = None
            revoked = False
            if connection_id:
                raw = self.vault.get(f"tokens:{connection_id}")
                if revoke and raw:
                    try:
                        response = httpx.post("https://oauth2.googleapis.com/revoke", data={"token": raw.get("refresh_token") or raw.get("token")}, timeout=15)
                        revoked = response.status_code == 200
                    except httpx.HTTPError:
                        pass
                self.vault.delete(f"tokens:{connection_id}")
                with self.db.session.begin() as session:
                    connection = session.get(Connection, connection_id)
                    if connection:
                        connection.status, connection.updated_at = "disconnected", now()
            return DisconnectResult(local_credentials_removed=True, remote_revoked=revoked,
                                    message="Đã xóa token cục bộ và thu hồi quyền Google." if revoked else "Đã xóa token cục bộ. Chưa xác nhận thu hồi quyền trên Google; dữ liệu SQLite được giữ lại.")
