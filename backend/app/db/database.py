import os
from pathlib import Path
import threading

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

BACKEND = Path(__file__).resolve().parents[2]


class Database:
    def __init__(self, path: Path | None = None):
        self.metrics_lock = threading.RLock()
        self.path = path or Path(os.environ.get("SEO_WORKSPACE_DATA_DIR", str(BACKEND / "data"))) / "seo_workspace.db"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.path.as_posix()}", connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(self.engine, "connect")
        def pragmas(connection, record):
            connection.execute("PRAGMA foreign_keys=ON")
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA busy_timeout=30000")

        self.session: sessionmaker[Session] = sessionmaker(self.engine, expire_on_commit=False)

    def migrate(self):
        config = Config()
        config.set_main_option("script_location", str(BACKEND / "migrations"))
        with self.engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")


if __name__ == "__main__":
    database = Database()
    database.migrate()
    print("SQLite schema is up to date.")
