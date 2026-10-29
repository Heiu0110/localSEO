"""API key entry stays in the terminal and OS vault, never frontend/CLI args/env."""

import argparse
import getpass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.gsc.vault import CredentialVault
from app.gsc.errors import GSCError
from app.db.database import Database
from app.db.models import Setting
from app.ai.provider import KEY_NAME, VALIDATION_KEY


def main():
    parser = argparse.ArgumentParser(
        description="Lưu OpenAI API key trong OS keyring, không có plaintext fallback."
    )
    parser.add_argument("--remove-key", action="store_true")
    args = parser.parse_args()
    vault = CredentialVault()
    try:
        if args.remove_key:
            vault.delete(KEY_NAME)
        else:
            key = getpass.getpass("OpenAI API key (ẩn khi nhập): ").strip()
            if not key or len(key) > 512:
                raise ValueError("Key trống hoặc quá dài.")
            vault.put(KEY_NAME, {"api_key": key})
        db = Database()
        db.migrate()
        with db.session.begin() as s:
            validation = s.get(Setting, VALIDATION_KEY)
            if validation:
                s.delete(validation)
        db.engine.dispose()
        print(
            "Đã xóa key."
            if args.remove_key
            else "Đã lưu key trong kho khóa hệ điều hành. Mở AI Settings để kiểm tra model và ngân sách."
        )
    except (GSCError, ValueError) as error:
        print(
            error.message if isinstance(error, GSCError) else str(error),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
