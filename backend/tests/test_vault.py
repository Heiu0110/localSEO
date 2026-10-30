"""Exercise the OS-vault storage contract without a real user's credentials."""
import json

import pytest

from app.gsc.errors import GSCError
from app.gsc.vault import CredentialVault, CHATGPT_TOKENS, SERVICE, CHUNK_MARKER


class SimulatedWinVault:
    def __init__(self):
        self.values = {}
        self.fail_write = None

    def get_password(self, service, key):
        assert service == SERVICE
        return self.values.get(key)

    def set_password(self, service, key, value):
        assert service == SERVICE
        if self.fail_write and self.fail_write(key):
            # A native Windows exception need not inherit keyring.KeyringError.
            raise Exception("native fixture failure; never echo fake-secret")
        if len(value.encode("utf-16-le")) > 2560:
            raise Exception("CredentialBlob exceeds Windows limit")
        self.values[key] = value

    def delete_password(self, service, key):
        assert service == SERVICE
        self.values.pop(key, None)


@pytest.fixture
def storage(monkeypatch):
    backend = SimulatedWinVault()
    vault = CredentialVault()
    monkeypatch.setattr(vault, "_backend", lambda: backend)
    return vault, backend


def tokens(suffix="one"):
    return {"access_token": "fake-access-" + "a" * 6000 + suffix,
            "refresh_token": "fake-refresh-" + "b" * 3000 + suffix,
            "account": {"name": "Tài khoản thử nghiệm"}, "session_id": suffix}


def test_long_chatgpt_tokens_fit_windows_entries_and_roundtrip(storage):
    vault, backend = storage
    expected = tokens()
    with pytest.raises(Exception, match="exceeds Windows limit"):
        backend.set_password(SERVICE, CHATGPT_TOKENS, json.dumps(expected))
    vault.put(CHATGPT_TOKENS, expected)
    assert vault.get(CHATGPT_TOKENS) == expected
    manifest = json.loads(backend.values[CHATGPT_TOKENS])
    assert manifest[CHUNK_MARKER] == 1 and manifest["count"] > 1
    assert "access_token" not in backend.values[CHATGPT_TOKENS]
    assert all(len(value.encode("utf-16-le")) <= 2560 for value in backend.values.values())


@pytest.mark.parametrize("failure", ["part", "commit"])
def test_failed_refresh_preserves_complete_previous_tokens_and_cleans_new_parts(storage, failure):
    vault, backend = storage
    old = tokens()
    vault.put(CHATGPT_TOKENS, old)
    active = json.loads(backend.values[CHATGPT_TOKENS])["slot"]
    inactive = "b" if active == "a" else "a"
    backend.fail_write = lambda key: key == (CHATGPT_TOKENS if failure == "commit"
                                           else f"{CHATGPT_TOKENS}.part.{inactive}.1")
    with pytest.raises(GSCError) as error:
        vault.put(CHATGPT_TOKENS, tokens("two"))
    assert "fake-secret" not in error.value.message
    assert vault.get(CHATGPT_TOKENS) == old
    assert not any(f".part.{inactive}." in key for key in backend.values)


@pytest.mark.parametrize("failure", ["missing", "modified"])
def test_incomplete_or_corrupted_token_parts_are_never_returned(storage, failure):
    vault, backend = storage
    vault.put(CHATGPT_TOKENS, tokens())
    manifest = json.loads(backend.values[CHATGPT_TOKENS])
    key = f"{CHATGPT_TOKENS}.part.{manifest['slot']}.0"
    if failure == "missing":
        del backend.values[key]
    else:
        backend.values[key] = "tampered fixture"
    with pytest.raises(GSCError):
        vault.get(CHATGPT_TOKENS)
    vault.delete(CHATGPT_TOKENS)
    assert not backend.values


def test_rotation_and_disconnect_remove_both_slots_including_interrupted_write(storage):
    vault, backend = storage
    vault.put("tokens:google-fixture", {"refresh_token": "fixture-google"})
    vault.put(CHATGPT_TOKENS, tokens())
    vault.put(CHATGPT_TOKENS, tokens("two"))
    manifest = json.loads(backend.values[CHATGPT_TOKENS])
    unused = "b" if manifest["slot"] == "a" else "a"
    backend.values[f"{CHATGPT_TOKENS}.part.{unused}.90"] = "orphan from an interrupted write"
    vault.delete(CHATGPT_TOKENS)
    assert not any(key.startswith(CHATGPT_TOKENS) for key in backend.values)
    assert vault.get("tokens:google-fixture") == {"refresh_token": "fixture-google"}


def test_legacy_tokens_remain_readable_and_non_chatgpt_storage_is_unchanged(storage):
    vault, backend = storage
    legacy = {"access_token": "legacy-fixture", "refresh_token": "old-fixture"}
    backend.values[CHATGPT_TOKENS] = json.dumps(legacy)
    assert vault.get(CHATGPT_TOKENS) == legacy
    vault.put(CHATGPT_TOKENS, tokens())
    assert vault.get(CHATGPT_TOKENS) == tokens()
    vault.put("ai.openai.api_key", {"api_key": "fake-key"})
    assert json.loads(backend.values["ai.openai.api_key"]) == {"api_key": "fake-key"}


def test_oversized_payload_does_not_replace_a_valid_credential(storage):
    vault, _ = storage
    vault.put(CHATGPT_TOKENS, tokens())
    with pytest.raises(GSCError):
        vault.put(CHATGPT_TOKENS, {"access_token": "x" * 100_000})
    assert vault.get(CHATGPT_TOKENS) == tokens()
