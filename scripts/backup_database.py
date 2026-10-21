"""Consistent SQLite backup, including committed WAL contents. Tokens are OS-managed."""
import argparse
import os
from pathlib import Path
import sqlite3
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]


def main():
    default_source = Path(os.environ.get("SEO_WORKSPACE_DATA_DIR", str(ROOT / "backend" / "data"))) / "seo_workspace.db"
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=default_source)
    parser.add_argument("--destination", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    destination = (args.destination or source.parent / "backups" / f"seo-workspace-{datetime.now():%Y%m%d-%H%M%S}.db").resolve()
    if not source.is_file():
        parser.error("Database chưa tồn tại. Khởi chạy backend trước.")
    if destination == source or destination.exists():
        parser.error("Không ghi đè database hoặc bản backup đã có. Chọn đường dẫn mới.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as original, sqlite3.connect(destination) as backup:
        original.backup(backup)
        if backup.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("Backup chưa vượt qua integrity_check; không dùng để restore.")
    print(f"SQLite backup verified: {destination}")
    print("OAuth tokens are not in the database. Reconnect Google on a different machine.")


if __name__ == "__main__":
    main()
