"""OS-managed credentials only. No file/SQLite/plaintext fallback."""
import json

import keyring
from keyring.errors import KeyringError

from app.gsc.errors import GSCError

SERVICE = "SEO Local Workspace v0.2"


class CredentialVault:
    def _backend(self):
        backend = keyring.get_keyring()
        allowed = ("keyring.backends.Windows", "keyring.backends.macOS", "keyring.backends.SecretService",
                   "keyring.backends.kwallet", "keyring.backends.libsecret")
        candidates = getattr(backend, "backends", [backend])
        for candidate in candidates:
            if candidate.__class__.__module__.startswith(allowed) and candidate.priority > 0:
                return candidate
        raise GSCError("secure_storage_unavailable", "Chưa có kho khóa hệ điều hành. Trên Windows hãy dùng Windows Credential Manager; không lưu token dạng văn bản.", 503)

    def get(self, key: str) -> dict | None:
        try:
            raw = self._backend().get_password(SERVICE, key)
            return json.loads(raw) if raw else None
        except (KeyringError, RuntimeError, ValueError) as exc:
            raise GSCError("secure_storage_unavailable", "Không thể mở kho khóa hệ điều hành. Hãy mở khóa kho khóa rồi thử lại.", 503) from None

    def put(self, key: str, value: dict):
        try:
            self._backend().set_password(SERVICE, key, json.dumps(value))
        except (KeyringError, RuntimeError) as exc:
            raise GSCError("secure_storage_unavailable", "Không thể ghi vào kho khóa hệ điều hành.", 503) from None

    def delete(self, key: str):
        try:
            backend = self._backend()
            if backend.get_password(SERVICE, key):
                backend.delete_password(SERVICE, key)
        except (KeyringError, RuntimeError) as exc:
            raise GSCError("secure_storage_unavailable", "Không thể xóa thông tin trong kho khóa hệ điều hành.", 503) from None
