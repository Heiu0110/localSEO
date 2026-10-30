"""OS-managed credentials only. No file/SQLite/plaintext fallback."""
import hashlib
import json
import re
from threading import RLock

import keyring

from app.gsc.errors import GSCError

SERVICE = "SEO Local Workspace v0.2"
CHATGPT_TOKENS = "ai.chatgpt.tokens.v1"
# WinVault stores strings as UTF-16 and limits each credential blob to 2560
# bytes. SIWC access/refresh JWTs can exceed that even without an ID token.
PART_SIZE = 900
MAX_PARTS = 96
CHUNK_MARKER = "_localseo_secure_chunks"
_LOCK = RLock()


class CredentialVault:
    @staticmethod
    def _part_key(key, slot, index):
        return f"{key}.part.{slot}.{index}"

    @staticmethod
    def _manifest(value):
        if not isinstance(value, dict) or CHUNK_MARKER not in value:
            return None
        if (value.get(CHUNK_MARKER) != 1 or value.get("slot") not in ("a", "b")
                or type(value.get("count")) is not int
                or not 1 <= value["count"] <= MAX_PARTS
                or not isinstance(value.get("digest"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", value["digest"])):
            raise ValueError("Invalid credential manifest")
        return value

    @staticmethod
    def _delete_entry(backend, key):
        if backend.get_password(SERVICE, key) is not None:
            backend.delete_password(SERVICE, key)

    def _clear_slot(self, backend, key, slot, *, strict=True):
        failed = False
        for index in range(MAX_PARTS):
            try:
                self._delete_entry(backend, self._part_key(key, slot, index))
            except Exception:
                failed = True
        if failed and strict:
            raise RuntimeError("Credential cleanup failed")
        return not failed

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
        with _LOCK:
            try:
                backend = self._backend()
                raw = backend.get_password(SERVICE, key)
                value = json.loads(raw) if raw else None
                if value is not None and not isinstance(value, dict):
                    raise ValueError("Credential object required")
                manifest = self._manifest(value) if key == CHATGPT_TOKENS else None
                if not manifest:
                    return value  # Existing Google/API-key and legacy SIWC entries.
                parts = [backend.get_password(SERVICE, self._part_key(key, manifest["slot"], i))
                         for i in range(manifest["count"])]
                if any(not isinstance(part, str) or not 1 <= len(part) <= PART_SIZE for part in parts):
                    raise ValueError("Incomplete credential")
                payload = "".join(parts)
                if hashlib.sha256(payload.encode("ascii")).hexdigest() != manifest["digest"]:
                    raise ValueError("Credential checksum mismatch")
                value = json.loads(payload)
                if not isinstance(value, dict):
                    raise ValueError("Invalid credential")
                return value
            except Exception:
                # Native pywintypes errors do not all inherit KeyringError.
                raise GSCError("secure_storage_unavailable", "Không thể mở hoặc đọc đầy đủ kho khóa hệ điều hành. Hãy mở khóa kho khóa; nếu token hỏng, ngắt kết nối và đăng nhập lại.", 503) from None

    def put(self, key: str, value: dict):
        with _LOCK:
            backend = None
            slot = None
            committed = False
            try:
                backend = self._backend()
                payload = json.dumps(value, ensure_ascii=True)
                if key != CHATGPT_TOKENS:
                    backend.set_password(SERVICE, key, payload)
                    return
                if len(payload) > PART_SIZE * MAX_PARTS:
                    raise ValueError("Credential too large")
                previous = backend.get_password(SERVICE, key)
                old = self._manifest(json.loads(previous)) if previous else None
                slot = "b" if old and old["slot"] == "a" else "a"
                self._clear_slot(backend, key, slot)
                parts = [payload[i:i + PART_SIZE] for i in range(0, len(payload), PART_SIZE)]
                for i, part in enumerate(parts):
                    backend.set_password(SERVICE, self._part_key(key, slot, i), part)
                manifest = {CHUNK_MARKER: 1, "slot": slot, "count": len(parts),
                            "digest": hashlib.sha256(payload.encode("ascii")).hexdigest()}
                # Publish only after every part is stored. A failed refresh keeps
                # the previous complete generation available for a later retry.
                backend.set_password(SERVICE, key, json.dumps(manifest))
                committed = True
                if old:
                    self._clear_slot(backend, key, old["slot"], strict=False)
            except Exception:
                if backend and slot and not committed:
                    self._clear_slot(backend, key, slot, strict=False)
                raise GSCError("secure_storage_unavailable", "Không thể ghi token vào kho khóa hệ điều hành. Kiểm tra Windows Credential Manager rồi thử đăng nhập lại.", 503) from None

    def delete(self, key: str):
        with _LOCK:
            try:
                backend = self._backend()
                self._delete_entry(backend, key)
                if key == CHATGPT_TOKENS:
                    # Both bounded slots are swept, including parts left by an
                    # interrupted write; no credential enumeration is required.
                    cleared_a = self._clear_slot(backend, key, "a", strict=False)
                    cleared_b = self._clear_slot(backend, key, "b", strict=False)
                    if not cleared_a or not cleared_b:
                        raise RuntimeError("Credential cleanup failed")
            except Exception:
                raise GSCError("secure_storage_unavailable", "Không thể xóa hết thông tin trong kho khóa hệ điều hành. Thử ngắt kết nối lại.", 503) from None
