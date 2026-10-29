"""Additive Phase 7 research storage. Frozen DDL; existing tables unchanged."""

from alembic import op

revision = "005_keyword_serp_research"
down_revision = "004_ai_agent"
branch_labels = depends_on = None
DDL = [
    """CREATE TABLE research_projects (
	id VARCHAR NOT NULL,
	local_project_id VARCHAR,
	name VARCHAR NOT NULL,
	description VARCHAR NOT NULL,
	business_context VARCHAR NOT NULL,
	research_goal VARCHAR NOT NULL,
	country VARCHAR NOT NULL,
	language VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	settings JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id)
)""",
    """CREATE TABLE research_clusters (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	primary_keyword_id VARCHAR,
	intent VARCHAR NOT NULL,
	page_type VARCHAR NOT NULL,
	target_url VARCHAR NOT NULL,
	mapping_status VARCHAR NOT NULL,
	notes VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	evidence JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES research_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_import_jobs (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES research_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_review_events (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	entity_type VARCHAR NOT NULL,
	entity_id VARCHAR NOT NULL,
	decision VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES research_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_keywords (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	keyword_text VARCHAR NOT NULL,
	normalized_keyword VARCHAR NOT NULL,
	country VARCHAR NOT NULL,
	language VARCHAR NOT NULL,
	group_name VARCHAR NOT NULL,
	intent VARCHAR NOT NULL,
	target_url VARCHAR NOT NULL,
	mapping_status VARCHAR NOT NULL,
	brand_label VARCHAR NOT NULL,
	notes VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	cluster_id VARCHAR,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, normalized_keyword, country, language),
	FOREIGN KEY(project_id) REFERENCES research_projects (id) ON DELETE CASCADE,
	FOREIGN KEY(cluster_id) REFERENCES research_clusters (id) ON DELETE SET NULL
)""",
    """CREATE TABLE research_keyword_sources (
	id VARCHAR NOT NULL,
	keyword_id VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	method VARCHAR NOT NULL,
	reference VARCHAR NOT NULL,
	original_text VARCHAR NOT NULL,
	seed VARCHAR NOT NULL,
	collected_at VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (keyword_id, identity),
	FOREIGN KEY(keyword_id) REFERENCES research_keywords (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_opportunities (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	keyword_id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	priority VARCHAR NOT NULL,
	confidence VARCHAR NOT NULL,
	proposed_action VARCHAR NOT NULL,
	evidence JSON NOT NULL,
	status VARCHAR NOT NULL,
	notes VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (keyword_id, kind),
	FOREIGN KEY(project_id) REFERENCES research_projects (id) ON DELETE CASCADE,
	FOREIGN KEY(keyword_id) REFERENCES research_keywords (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_serp_snapshots (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	keyword_id VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	search_engine VARCHAR NOT NULL,
	search_type VARCHAR NOT NULL,
	country VARCHAR NOT NULL,
	language VARCHAR NOT NULL,
	location VARCHAR NOT NULL,
	device VARCHAR NOT NULL,
	requested_depth INTEGER NOT NULL,
	returned_depth INTEGER NOT NULL,
	collected_at VARCHAR NOT NULL,
	completeness VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, identity),
	FOREIGN KEY(project_id) REFERENCES research_projects (id) ON DELETE CASCADE,
	FOREIGN KEY(keyword_id) REFERENCES research_keywords (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_keyword_metrics (
	id VARCHAR NOT NULL,
	source_id VARCHAR NOT NULL,
	metric_type VARCHAR NOT NULL,
	value DOUBLE NOT NULL,
	unit VARCHAR NOT NULL,
	scope VARCHAR NOT NULL,
	reporting_start VARCHAR,
	reporting_end VARCHAR,
	metadata_json JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (source_id, metric_type),
	CHECK (value >= 0),
	FOREIGN KEY(source_id) REFERENCES research_keyword_sources (id) ON DELETE CASCADE
)""",
    """CREATE TABLE research_serp_results (
	id VARCHAR NOT NULL,
	snapshot_id VARCHAR NOT NULL,
	organic_position INTEGER,
	provider_position VARCHAR NOT NULL,
	result_type VARCHAR NOT NULL,
	title VARCHAR NOT NULL,
	url VARCHAR NOT NULL,
	normalized_url VARCHAR NOT NULL,
	domain VARCHAR NOT NULL,
	snippet VARCHAR NOT NULL,
	features JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(snapshot_id) REFERENCES research_serp_snapshots (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_research_project_site ON research_projects (local_project_id, status)""",
    """CREATE INDEX ix_research_cluster_project ON research_clusters (project_id, status)""",
    """CREATE INDEX ix_research_members ON research_keywords (cluster_id)""",
    """CREATE INDEX ix_research_keyword_lookup ON research_keywords (project_id, status, normalized_keyword)""",
    """CREATE INDEX ix_research_opportunities ON research_opportunities (project_id, status)""",
    """CREATE INDEX ix_research_serp_lookup ON research_serp_snapshots (project_id, keyword_id, collected_at)""",
    """CREATE INDEX ix_research_serp_results ON research_serp_results (snapshot_id, organic_position)""",
]


def upgrade():
    for sql in DDL:
        op.execute(sql)


def downgrade():
    for name in [
        "research_serp_results",
        "research_keyword_metrics",
        "research_serp_snapshots",
        "research_opportunities",
        "research_keyword_sources",
        "research_keywords",
        "research_review_events",
        "research_import_jobs",
        "research_clusters",
        "research_projects",
    ]:
        op.execute("DROP TABLE " + name)
