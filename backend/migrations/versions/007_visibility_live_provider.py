"""Additive live collection audit; existing observations and shared usage preserved."""

from alembic import op

revision = "007_visibility_live_provider"
down_revision = "006_ai_visibility"
branch_labels = depends_on = None
DDL = [
    """CREATE TABLE visibility_collection_requests (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	prompt_id VARCHAR NOT NULL,
	request_key VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	active_slot INTEGER,
	binding_hash VARCHAR NOT NULL,
	snapshot JSON NOT NULL,
	result JSON NOT NULL,
	observation_id VARCHAR,
	usage_id VARCHAR,
	dispatched_at VARCHAR,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (project_id, request_key),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id),
	FOREIGN KEY(prompt_id) REFERENCES visibility_prompts (id),
	UNIQUE (active_slot),
	FOREIGN KEY(observation_id) REFERENCES visibility_observations (id),
	FOREIGN KEY(usage_id) REFERENCES ai_usage_records (id)
)""",
    """CREATE INDEX ix_visibility_collection_project ON visibility_collection_requests (project_id, created_at)""",
    """CREATE TABLE visibility_collection_consents (
	id VARCHAR NOT NULL,
	request_id VARCHAR NOT NULL,
	binding_hash VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (request_id),
	FOREIGN KEY(request_id) REFERENCES visibility_collection_requests (id)
)""",
    """CREATE TABLE visibility_search_sources (
	id VARCHAR NOT NULL,
	request_id VARCHAR NOT NULL,
	observation_id VARCHAR,
	project_id VARCHAR NOT NULL,
	normalized_url VARCHAR NOT NULL,
	data JSON NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(request_id) REFERENCES visibility_collection_requests (id),
	FOREIGN KEY(observation_id) REFERENCES visibility_observations (id),
	FOREIGN KEY(project_id) REFERENCES visibility_projects (id)
)""",
    """CREATE INDEX ix_visibility_search_sources ON visibility_search_sources (project_id, observation_id)""",
]


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    for name in (
        "visibility_search_sources",
        "visibility_collection_consents",
        "visibility_collection_requests",
    ):
        op.drop_table(name)
