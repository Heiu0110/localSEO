"""Phase 6 agent-owned storage. Existing SEO tables are untouched."""

from alembic import op

revision = "004_ai_agent"
down_revision = "003_keyword_tracking"
branch_labels = depends_on = None

DDL = [
    """CREATE TABLE ai_conversations (
	id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	title VARCHAR NOT NULL,
	provider VARCHAR NOT NULL,
	model VARCHAR NOT NULL,
	saved BOOLEAN NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id)
)""",
    """CREATE TABLE ai_messages (
	id VARCHAR NOT NULL,
	conversation_id VARCHAR NOT NULL,
	role VARCHAR NOT NULL,
	content VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	request_key VARCHAR,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE
)""",
    """CREATE TABLE ai_evidence_references (
	id VARCHAR NOT NULL,
	message_id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	source_type VARCHAR NOT NULL,
	source_record_id VARCHAR,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(message_id) REFERENCES ai_messages (id) ON DELETE CASCADE
)""",
    """CREATE TABLE ai_recommendations (
	id VARCHAR NOT NULL,
	conversation_id VARCHAR NOT NULL,
	message_id VARCHAR NOT NULL,
	project_id VARCHAR NOT NULL,
	title VARCHAR NOT NULL,
	proposed_action VARCHAR NOT NULL,
	priority VARCHAR NOT NULL,
	confidence VARCHAR NOT NULL,
	evidence_ids JSON NOT NULL,
	approval_status VARCHAR NOT NULL,
	user_notes VARCHAR NOT NULL,
	reviewed_at VARCHAR,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(conversation_id) REFERENCES ai_conversations (id) ON DELETE CASCADE,
	FOREIGN KEY(message_id) REFERENCES ai_messages (id) ON DELETE CASCADE
)""",
    """CREATE TABLE ai_tool_executions (
	id VARCHAR NOT NULL,
	message_id VARCHAR NOT NULL,
	tool_name VARCHAR NOT NULL,
	tool_version VARCHAR NOT NULL,
	input_summary JSON NOT NULL,
	output_summary JSON NOT NULL,
	status VARCHAR NOT NULL,
	duration_ms INTEGER NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(message_id) REFERENCES ai_messages (id) ON DELETE CASCADE
)""",
    """CREATE TABLE ai_usage_records (
	id VARCHAR NOT NULL,
	message_id VARCHAR,
	provider VARCHAR NOT NULL,
	model VARCHAR NOT NULL,
	request_id VARCHAR,
	status VARCHAR NOT NULL,
	input_tokens INTEGER,
	output_tokens INTEGER,
	reserved_usd DOUBLE NOT NULL,
	estimated_cost_usd DOUBLE,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(message_id) REFERENCES ai_messages (id) ON DELETE SET NULL
)""",
    """CREATE INDEX ix_ai_conversation_project ON ai_conversations (project_id, updated_at)""",
    """CREATE UNIQUE INDEX ix_ai_active_turn ON ai_messages (conversation_id) WHERE role='assistant' AND status IN ('queued','running')""",
    """CREATE UNIQUE INDEX ix_ai_idempotency ON ai_messages (conversation_id, request_key) WHERE request_key IS NOT NULL""",
    """CREATE INDEX ix_ai_message_history ON ai_messages (conversation_id, created_at)""",
    """CREATE INDEX ix_ai_evidence_message ON ai_evidence_references (message_id)""",
    """CREATE INDEX ix_ai_recommendation_project ON ai_recommendations (project_id, approval_status)""",
    """CREATE INDEX ix_ai_tools_message ON ai_tool_executions (message_id, created_at)""",
    """CREATE INDEX ix_ai_usage_day ON ai_usage_records (created_at, status)""",
]


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    for name in [
        "ai_usage_records",
        "ai_tool_executions",
        "ai_recommendations",
        "ai_evidence_references",
        "ai_messages",
        "ai_conversations",
    ]:
        op.execute("DROP TABLE " + name)
