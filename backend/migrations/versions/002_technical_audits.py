"""Additive Technical SEO snapshots; never rebuild or drop GSC storage."""
from alembic import op

revision = "002_technical_audits"
down_revision = "001_gsc_storage"
branch_labels = depends_on = None

DDL = [
    """CREATE TABLE technical_projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, root_url TEXT NOT NULL,
    property_id TEXT REFERENCES gsc_properties(id), source_type TEXT NOT NULL, config JSON NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""",
    """CREATE TABLE technical_audits (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES technical_projects(id),
    name TEXT NOT NULL, status TEXT NOT NULL, config JSON NOT NULL, scope_hash TEXT NOT NULL, rule_version TEXT NOT NULL,
    phase TEXT NOT NULL, processed INTEGER NOT NULL DEFAULT 0, requests INTEGER NOT NULL DEFAULT 0,
    cancel_requested BOOLEAN NOT NULL DEFAULT 0, coverage JSON NOT NULL, summary JSON NOT NULL,
    started_at TEXT NOT NULL, finished_at TEXT, error TEXT)""",
    "CREATE INDEX ix_technical_runs ON technical_audits(project_id, started_at)",
    "CREATE UNIQUE INDEX ix_technical_active ON technical_audits(project_id) WHERE status IN ('queued','running')",
    """CREATE TABLE technical_urls (id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES technical_audits(id) ON DELETE CASCADE,
    url TEXT NOT NULL, original_url TEXT NOT NULL, final_url TEXT, state TEXT NOT NULL, status_code INTEGER, depth INTEGER,
    title TEXT NOT NULL DEFAULT '', indexability TEXT NOT NULL DEFAULT 'unknown', inbound INTEGER NOT NULL DEFAULT 0,
    outbound INTEGER NOT NULL DEFAULT 0, duration_ms REAL, sources JSON NOT NULL, data JSON NOT NULL, crawled_at TEXT,
    UNIQUE(audit_id,url))""",
    "CREATE INDEX ix_technical_url_report ON technical_urls(audit_id, indexability, status_code)",
    """CREATE TABLE technical_links (id INTEGER PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES technical_audits(id) ON DELETE CASCADE,
    source_id TEXT NOT NULL REFERENCES technical_urls(id) ON DELETE CASCADE, target_url TEXT NOT NULL, anchor TEXT NOT NULL,
    rel TEXT NOT NULL, context TEXT NOT NULL, internal BOOLEAN NOT NULL)""",
    "CREATE INDEX ix_technical_links ON technical_links(audit_id, target_url)",
    """CREATE TABLE technical_sitemaps (id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES technical_audits(id) ON DELETE CASCADE,
    url TEXT NOT NULL, status_code INTEGER, data JSON NOT NULL, UNIQUE(audit_id,url))""",
    """CREATE TABLE technical_issues (id TEXT PRIMARY KEY, audit_id TEXT NOT NULL REFERENCES technical_audits(id) ON DELETE CASCADE,
    project_id TEXT NOT NULL REFERENCES technical_projects(id), url_id TEXT REFERENCES technical_urls(id) ON DELETE CASCADE,
    fingerprint TEXT NOT NULL, url TEXT NOT NULL, rule_id TEXT NOT NULL, category TEXT NOT NULL, title TEXT NOT NULL,
    severity TEXT NOT NULL, confidence TEXT NOT NULL, evidence_type TEXT NOT NULL, evidence JSON NOT NULL,
    recommendation TEXT NOT NULL, verification TEXT NOT NULL, priority INTEGER NOT NULL, priority_reasons JSON NOT NULL,
    first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, UNIQUE(audit_id,fingerprint))""",
    "CREATE INDEX ix_technical_issues ON technical_issues(audit_id, severity, rule_id, priority)",
    """CREATE TABLE technical_tasks (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES technical_projects(id),
    fingerprint TEXT NOT NULL, rule_id TEXT NOT NULL, url TEXT NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL,
    status TEXT NOT NULL, owner TEXT NOT NULL DEFAULT '', notes TEXT NOT NULL DEFAULT '', verification TEXT NOT NULL,
    verification_audit_id TEXT, priority INTEGER NOT NULL, first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL,
    UNIQUE(project_id,fingerprint))""",
    "CREATE INDEX ix_technical_tasks ON technical_tasks(project_id,status,priority)",
    """CREATE TABLE technical_url_intents (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES technical_projects(id),
    url TEXT NOT NULL, importance TEXT NOT NULL, should_index TEXT NOT NULL, page_type TEXT NOT NULL, notes TEXT NOT NULL,
    source TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(project_id,url))""",
    """CREATE TABLE technical_imports (id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES technical_projects(id),
    filename TEXT NOT NULL, digest TEXT NOT NULL, status TEXT NOT NULL, rows JSON NOT NULL, created_at TEXT NOT NULL)""",
]


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    for table in ("technical_imports", "technical_url_intents", "technical_tasks", "technical_issues", "technical_sitemaps",
                  "technical_links", "technical_urls", "technical_audits", "technical_projects"):
        op.execute(f"DROP TABLE {table}")
