"""Keyword metadata and append-only, independently measured rank history."""

from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base


class KeywordSet(Base):
    __tablename__ = "keyword_sets"
    id: Mapped[str] = mapped_column(primary_key=True)
    site_id: Mapped[str]
    property_id: Mapped[str | None] = mapped_column(ForeignKey("gsc_properties.id"))
    name: Mapped[str]
    description: Mapped[str]
    start_date: Mapped[str]
    week_start_day: Mapped[int]
    timezone: Mapped[str]
    status: Mapped[str]
    settings: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (Index("ix_keyword_sets_site", "site_id"),)


class KeywordGroup(Base):
    __tablename__ = "keyword_groups"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    name: Mapped[str]
    color: Mapped[str]
    sort_order: Mapped[int]
    __table_args__ = (UniqueConstraint("keyword_set_id", "name"),)


class SearchProfile(Base):
    __tablename__ = "search_profiles"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    name: Mapped[str]
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]


class TrackedKeyword(Base):
    __tablename__ = "tracked_keywords"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    keyword_text: Mapped[str]
    normalized_keyword: Mapped[str]
    group_id: Mapped[str | None] = mapped_column(ForeignKey("keyword_groups.id"))
    target_url: Mapped[str]
    match_mode: Mapped[str]
    priority: Mapped[str]
    search_intent: Mapped[str]
    status: Mapped[str]
    notes: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("keyword_set_id", "normalized_keyword"),
        Index("ix_keyword_lookup", "keyword_set_id", "status", "normalized_keyword"),
    )


class TrackingWeek(Base):
    __tablename__ = "tracking_weeks"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    week_number: Mapped[int]
    start_date: Mapped[str]
    end_date: Mapped[str]
    __table_args__ = (
        UniqueConstraint("keyword_set_id", "week_number"),
        CheckConstraint("week_number > 0"),
    )


class RankObservation(Base):
    __tablename__ = "keyword_rank_observations"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tracked_keyword_id: Mapped[str] = mapped_column(
        ForeignKey("tracked_keywords.id", ondelete="CASCADE")
    )
    tracking_week_id: Mapped[str] = mapped_column(
        ForeignKey("tracking_weeks.id", ondelete="CASCADE")
    )
    search_profile_id: Mapped[str] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="CASCADE")
    )
    checked_at: Mapped[str | None]
    timestamp_precision: Mapped[str]
    checked_by: Mapped[str]
    rank_status: Mapped[str]
    rank_value: Mapped[int | None]
    method: Mapped[str]
    matched_url: Mapped[str]
    target_url_snapshot: Mapped[str]
    match_mode: Mapped[str]
    profile_snapshot: Mapped[dict] = mapped_column(JSON)
    series_key: Mapped[str]
    notes: Mapped[str]
    created_at: Mapped[str]
    __table_args__ = (
        Index(
            "ix_rank_profile_week",
            "search_profile_id",
            "tracking_week_id",
            "tracked_keyword_id",
            "id",
        ),
        Index(
            "ix_rank_representative",
            "tracked_keyword_id",
            "search_profile_id",
            "tracking_week_id",
            "id",
        ),
        CheckConstraint(
            "(rank_status='FOUND' AND rank_value IS NOT NULL AND rank_value>=1) OR (rank_status IN ('NOT_FOUND','NOT_CHECKED') AND rank_value IS NULL)"
        ),
    )


class KeywordMetric(Base):
    __tablename__ = "keyword_gsc_metrics"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_id: Mapped[str] = mapped_column(
        ForeignKey("tracked_keywords.id", ondelete="CASCADE")
    )
    scope: Mapped[str]
    date_start: Mapped[str]
    date_end: Mapped[str]
    identity: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("keyword_id", "scope", "date_start", "date_end", "identity"),
    )


class KeywordSyncJob(Base):
    __tablename__ = "keyword_gsc_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    status: Mapped[str]
    completed: Mapped[int]
    total: Mapped[int]
    data: Mapped[dict] = mapped_column(JSON)
    error: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        Index(
            "ix_keyword_active_sync",
            "keyword_set_id",
            unique=True,
            sqlite_where=text("status IN ('queued','running')"),
        ),
    )


class KeywordImport(Base):
    __tablename__ = "keyword_import_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    filename: Mapped[str]
    status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class TrackingActivity(Base):
    __tablename__ = "keyword_tracking_activity"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    keyword_set_id: Mapped[str] = mapped_column(
        ForeignKey("keyword_sets.id", ondelete="CASCADE")
    )
    keyword_id: Mapped[str | None] = mapped_column(
        ForeignKey("tracked_keywords.id", ondelete="SET NULL")
    )
    action: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
