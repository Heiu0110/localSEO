"""Additive keyword tracking; GSC and Technical tables remain untouched."""

from alembic import op

revision = "003_keyword_tracking"
down_revision = "002_technical_audits"
branch_labels = depends_on = None

DDL = [
    """CREATE TABLE keyword_sets (
	id VARCHAR NOT NULL,
	site_id VARCHAR NOT NULL,
	property_id VARCHAR,
	name VARCHAR NOT NULL,
	description VARCHAR NOT NULL,
	start_date VARCHAR NOT NULL,
	week_start_day INTEGER NOT NULL,
	timezone VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	settings JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(property_id) REFERENCES gsc_properties (id)
)""",
    """CREATE TABLE keyword_groups (
	id VARCHAR NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	color VARCHAR NOT NULL,
	sort_order INTEGER NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (keyword_set_id, name),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE
)""",
    """CREATE TABLE keyword_gsc_jobs (
	id VARCHAR NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	completed INTEGER NOT NULL,
	total INTEGER NOT NULL,
	data JSON NOT NULL,
	error VARCHAR,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE
)""",
    """CREATE TABLE keyword_import_jobs (
	id VARCHAR NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	filename VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE
)""",
    """CREATE TABLE search_profiles (
	id VARCHAR NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	name VARCHAR NOT NULL,
	config JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE
)""",
    """CREATE TABLE tracking_weeks (
	id VARCHAR NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	week_number INTEGER NOT NULL,
	start_date VARCHAR NOT NULL,
	end_date VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (keyword_set_id, week_number),
	CHECK (week_number > 0),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE
)""",
    """CREATE TABLE tracked_keywords (
	id VARCHAR NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	keyword_text VARCHAR NOT NULL,
	normalized_keyword VARCHAR NOT NULL,
	group_id VARCHAR,
	target_url VARCHAR NOT NULL,
	match_mode VARCHAR NOT NULL,
	priority VARCHAR NOT NULL,
	search_intent VARCHAR NOT NULL,
	status VARCHAR NOT NULL,
	notes VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	updated_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (keyword_set_id, normalized_keyword),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE,
	FOREIGN KEY(group_id) REFERENCES keyword_groups (id)
)""",
    """CREATE TABLE keyword_gsc_metrics (
	id VARCHAR NOT NULL,
	keyword_id VARCHAR NOT NULL,
	scope VARCHAR NOT NULL,
	date_start VARCHAR NOT NULL,
	date_end VARCHAR NOT NULL,
	identity VARCHAR NOT NULL,
	data JSON NOT NULL,
	fetched_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	UNIQUE (keyword_id, scope, date_start, date_end, identity),
	FOREIGN KEY(keyword_id) REFERENCES tracked_keywords (id) ON DELETE CASCADE
)""",
    """CREATE TABLE keyword_rank_observations (
	id INTEGER NOT NULL,
	tracked_keyword_id VARCHAR NOT NULL,
	tracking_week_id VARCHAR NOT NULL,
	search_profile_id VARCHAR NOT NULL,
	checked_at VARCHAR,
	timestamp_precision VARCHAR NOT NULL,
	checked_by VARCHAR NOT NULL,
	rank_status VARCHAR NOT NULL,
	rank_value INTEGER,
	method VARCHAR NOT NULL,
	matched_url VARCHAR NOT NULL,
	target_url_snapshot VARCHAR NOT NULL,
	match_mode VARCHAR NOT NULL,
	profile_snapshot JSON NOT NULL,
	series_key VARCHAR NOT NULL,
	notes VARCHAR NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	CHECK ((rank_status='FOUND' AND rank_value IS NOT NULL AND rank_value>=1) OR (rank_status IN ('NOT_FOUND','NOT_CHECKED') AND rank_value IS NULL)),
	FOREIGN KEY(tracked_keyword_id) REFERENCES tracked_keywords (id) ON DELETE CASCADE,
	FOREIGN KEY(tracking_week_id) REFERENCES tracking_weeks (id) ON DELETE CASCADE,
	FOREIGN KEY(search_profile_id) REFERENCES search_profiles (id) ON DELETE CASCADE
)""",
    """CREATE TABLE keyword_tracking_activity (
	id INTEGER NOT NULL,
	keyword_set_id VARCHAR NOT NULL,
	keyword_id VARCHAR,
	action VARCHAR NOT NULL,
	data JSON NOT NULL,
	created_at VARCHAR NOT NULL,
	PRIMARY KEY (id),
	FOREIGN KEY(keyword_set_id) REFERENCES keyword_sets (id) ON DELETE CASCADE,
	FOREIGN KEY(keyword_id) REFERENCES tracked_keywords (id) ON DELETE SET NULL
)""",
    """CREATE INDEX ix_keyword_sets_site ON keyword_sets (site_id)""",
    """CREATE UNIQUE INDEX ix_keyword_active_sync ON keyword_gsc_jobs (keyword_set_id) WHERE status IN ('queued','running')""",
    """CREATE INDEX ix_keyword_lookup ON tracked_keywords (keyword_set_id, status, normalized_keyword)""",
    """CREATE INDEX ix_rank_representative ON keyword_rank_observations (tracked_keyword_id, search_profile_id, tracking_week_id, id)""",
    """CREATE INDEX ix_rank_profile_week ON keyword_rank_observations (search_profile_id, tracking_week_id, tracked_keyword_id, id)""",
]


def upgrade():
    for statement in DDL:
        op.execute(statement)


def downgrade():
    for name in [
        "keyword_tracking_activity",
        "keyword_rank_observations",
        "keyword_gsc_metrics",
        "tracked_keywords",
        "tracking_weeks",
        "search_profiles",
        "keyword_import_jobs",
        "keyword_gsc_jobs",
        "keyword_groups",
        "keyword_sets",
    ]:
        op.execute("DROP TABLE " + name)
