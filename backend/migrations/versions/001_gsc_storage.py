"""Initial immutable schema; subsequent schema changes require a new revision."""
from alembic import op

revision = "001_gsc_storage"
down_revision = None
branch_labels = None
depends_on = None

DDL = [
    """CREATE TABLE google_connections (
        id TEXT PRIMARY KEY, display_name TEXT NOT NULL, provider TEXT NOT NULL,
        status TEXT NOT NULL, scope TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE gsc_properties (
        id TEXT PRIMARY KEY, connection_id TEXT NOT NULL REFERENCES google_connections(id),
        site_url TEXT NOT NULL, display_name TEXT NOT NULL, property_type TEXT NOT NULL,
        permission_level TEXT NOT NULL, source_type TEXT NOT NULL, is_active BOOLEAN NOT NULL DEFAULT 0,
        added_at TEXT NOT NULL, last_synced_at TEXT,
        UNIQUE(connection_id, site_url))""",
    """CREATE TABLE gsc_daily_metrics (
        id INTEGER PRIMARY KEY, property_id TEXT NOT NULL REFERENCES gsc_properties(id),
        date TEXT NOT NULL, search_type TEXT NOT NULL, dataset_type TEXT NOT NULL,
        dimension_value TEXT NOT NULL, aggregation_type TEXT NOT NULL,
        clicks INTEGER NOT NULL CHECK(clicks >= 0), impressions INTEGER NOT NULL CHECK(impressions >= 0),
        ctr REAL NOT NULL, position REAL NOT NULL, data_state TEXT NOT NULL, fetched_at TEXT NOT NULL,
        UNIQUE(property_id, date, search_type, dataset_type, dimension_value, aggregation_type))""",
    "CREATE INDEX ix_metrics_report ON gsc_daily_metrics(property_id, search_type, dataset_type, date)",
    "CREATE INDEX ix_metrics_dimension ON gsc_daily_metrics(property_id, dataset_type, dimension_value)",
    """CREATE TABLE gsc_sync_checkpoints (
        id INTEGER PRIMARY KEY, property_id TEXT NOT NULL REFERENCES gsc_properties(id),
        search_type TEXT NOT NULL, dataset_type TEXT NOT NULL, date TEXT NOT NULL,
        status TEXT NOT NULL, completeness TEXT NOT NULL, fetched_rows INTEGER NOT NULL,
        aggregation_type TEXT NOT NULL, last_successful_sync_at TEXT NOT NULL,
        UNIQUE(property_id, search_type, dataset_type, date))""",
    """CREATE TABLE gsc_sync_jobs (
        id TEXT PRIMARY KEY, property_id TEXT NOT NULL REFERENCES gsc_properties(id),
        search_type TEXT NOT NULL, sync_mode TEXT NOT NULL, status TEXT NOT NULL,
        requested_date_start TEXT NOT NULL, requested_date_end TEXT NOT NULL,
        completed_days INTEGER NOT NULL DEFAULT 0, total_days INTEGER NOT NULL,
        rows_fetched INTEGER NOT NULL DEFAULT 0, current_task TEXT NOT NULL DEFAULT '',
        retry_count INTEGER NOT NULL DEFAULT 0, cancel_requested BOOLEAN NOT NULL DEFAULT 0,
        started_at TEXT NOT NULL, updated_at TEXT NOT NULL, finished_at TEXT, error_code TEXT, error_message TEXT)""",
    "CREATE INDEX ix_jobs_property ON gsc_sync_jobs(property_id, status, started_at)",
    "CREATE UNIQUE INDEX ix_one_active_job ON gsc_sync_jobs(property_id) WHERE status IN ('queued', 'running')",
    "CREATE TABLE app_settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)",
]


def upgrade():
    for sql in DDL:
        op.execute(sql)


def downgrade():
    for table in ("app_settings", "gsc_sync_jobs", "gsc_sync_checkpoints", "gsc_daily_metrics", "gsc_properties", "google_connections"):
        op.execute(f"DROP TABLE {table}")
