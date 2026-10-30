"""Frozen additive DDL for AI Visibility v0.8; source SEO tables unchanged."""

from alembic import op

revision = "006_ai_visibility"
down_revision = "005_keyword_serp_research"
branch_labels = depends_on = None

DDL = [
    """CREATE TABLE visibility_projects (
	id VARCHAR NOT NULL,
	local_project_id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	country VARCHAR NOT NULL,
	language VARCHAR NOT NULL,
	description VARCHAR NOT NULL,
	research_goal VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id)
)""",
    """CREATE INDEX ix_visibility_site ON visibility_projects (local_project_id, status)""",
    """CREATE TABLE visibility_detection_runs (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	scope JSON NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_documents (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	url VARCHAR NOT NULL,
	content VARCHAR NOT NULL,
	approved BOOLEAN NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_entities (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	config JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, kind, name),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_evidence (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	source_type VARCHAR NOT NULL,
	source_id VARCHAR NOT NULL,
	signature VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, source_type, source_id, signature),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_import_jobs (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	kind VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, kind, identity),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_opportunities (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	rule_id VARCHAR NOT NULL,
	title VARCHAR NOT NULL,
	category VARCHAR NOT NULL,
	priority VARCHAR NOT NULL,
	review_status VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, identity),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_visibility_opportunity ON visibility_opportunities (project_id, review_status, rule_id)""",
    """CREATE TABLE visibility_prompts (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	text VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	category VARCHAR NOT NULL,
	intent VARCHAR NOT NULL,
	cohort_type VARCHAR NOT NULL,
	priority INTEGER NOT NULL,
	status VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, identity),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE INDEX ix_visibility_prompt ON visibility_prompts (project_id, status, category)""",
    """CREATE TABLE visibility_reviews (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	entity_type VARCHAR NOT NULL,
	entity_id VARCHAR NOT NULL,
	decision VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_agent_analyses (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	opportunity_id VARCHAR NOT NULL,
	message_id VARCHAR,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE,
	FOREIGN KEY(opportunity_id) REFERENCES visibility_opportunities (id) ON DELETE CASCADE,
	FOREIGN KEY(message_id) REFERENCES ai_messages (id) ON DELETE SET NULL
)""",
    """CREATE TABLE visibility_coverage_reviews (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	requirement_id VARCHAR NOT NULL,
	page_id VARCHAR NOT NULL,
	decision VARCHAR NOT NULL,
	reason VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE,
	FOREIGN KEY(requirement_id) REFERENCES visibility_documents (id),
	FOREIGN KEY(page_id) REFERENCES visibility_documents (id)
)""",
    """CREATE TABLE visibility_observations (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	prompt_id VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	model VARCHAR,
	collection_method VARCHAR NOT NULL,
	prompt_snapshot VARCHAR NOT NULL,
	response_text VARCHAR NOT NULL,
	observed_at VARCHAR,
	imported_at VARCHAR NOT NULL,
	completeness VARCHAR NOT NULL,
	citation_capability VARCHAR NOT NULL,
	citation_metadata VARCHAR NOT NULL,
	supersedes_id VARCHAR,
	original JSON NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, identity),
	UNIQUE (supersedes_id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id) ON DELETE CASCADE,
	FOREIGN KEY(prompt_id) REFERENCES visibility_prompts (id),
	FOREIGN KEY(supersedes_id) REFERENCES visibility_observations (id)
)""",
    """CREATE INDEX ix_visibility_observation ON visibility_observations (project_id, provider, model, observed_at)""",
    """CREATE INDEX ix_visibility_observation_prompt ON visibility_observations (prompt_id)""",
    """CREATE TABLE visibility_extractions (
	id VARCHAR NOT NULL,
	observation_id VARCHAR NOT NULL,
	revision INTEGER NOT NULL,
	registry_hash VARCHAR NOT NULL,
	config_snapshot JSON NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (observation_id, revision),
	FOREIGN KEY(observation_id) REFERENCES visibility_observations (id) ON DELETE CASCADE
)""",
    """CREATE TABLE visibility_citations (
	id VARCHAR NOT NULL,
	extraction_id VARCHAR NOT NULL,
	entity_id VARCHAR,
	raw_url VARCHAR NOT NULL,
	normalized_url VARCHAR NOT NULL,
	domain VARCHAR NOT NULL,
	source_type VARCHAR NOT NULL,
	ownership VARCHAR NOT NULL,
	attribution_status VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(extraction_id) REFERENCES visibility_extractions (id) ON DELETE CASCADE,
	FOREIGN KEY(entity_id) REFERENCES visibility_entities (id)
)""",
    """CREATE INDEX ix_visibility_citation_domain ON visibility_citations (domain)""",
    """CREATE INDEX ix_visibility_citation_entity ON visibility_citations (entity_id, ownership)""",
    """CREATE TABLE visibility_mentions (
	id VARCHAR NOT NULL,
	extraction_id VARCHAR NOT NULL,
	entity_id VARCHAR NOT NULL,
	start INTEGER NOT NULL,
	"end" INTEGER NOT NULL,
	matched_text VARCHAR NOT NULL,
	alias VARCHAR NOT NULL,
	detected_status VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	reason VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(extraction_id) REFERENCES visibility_extractions (id) ON DELETE CASCADE,
	FOREIGN KEY(entity_id) REFERENCES visibility_entities (id)
)""",
    """CREATE INDEX ix_visibility_entity_mention ON visibility_mentions (entity_id, status)""",
]


def upgrade():
    for sql in DDL:
        op.execute(sql)


def downgrade():
    for name in [
        "visibility_mentions",
        "visibility_citations",
        "visibility_extractions",
        "visibility_observations",
        "visibility_coverage_reviews",
        "visibility_agent_analyses",
        "visibility_reviews",
        "visibility_prompts",
        "visibility_opportunities",
        "visibility_import_jobs",
        "visibility_evidence",
        "visibility_entities",
        "visibility_documents",
        "visibility_detection_runs",
        "visibility_projects",
    ]:
        op.execute("DROP TABLE " + name)
