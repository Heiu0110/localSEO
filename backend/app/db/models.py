"""Persistence models. Tokens and OAuth client JSON never enter this database."""
from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Connection(Base):
    __tablename__ = "google_connections"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    scope: Mapped[str] = mapped_column(String)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class Property(Base):
    __tablename__ = "gsc_properties"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("google_connections.id"))
    site_url: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(Text)
    property_type: Mapped[str] = mapped_column(String)
    permission_level: Mapped[str] = mapped_column(String)
    source_type: Mapped[str] = mapped_column(String)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[str] = mapped_column(String)
    last_synced_at: Mapped[str | None] = mapped_column(String, nullable=True)


class MetricFact(Base):
    __tablename__ = "gsc_daily_metrics"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("gsc_properties.id"))
    date: Mapped[str] = mapped_column(String)
    search_type: Mapped[str] = mapped_column(String)
    dataset_type: Mapped[str] = mapped_column(String)
    dimension_value: Mapped[str] = mapped_column(Text)
    aggregation_type: Mapped[str] = mapped_column(String)
    clicks: Mapped[int] = mapped_column(Integer)
    impressions: Mapped[int] = mapped_column(Integer)
    ctr: Mapped[float] = mapped_column(Float)
    position: Mapped[float] = mapped_column(Float)
    data_state: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[str] = mapped_column(String)


class Checkpoint(Base):
    __tablename__ = "gsc_sync_checkpoints"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("gsc_properties.id"))
    search_type: Mapped[str] = mapped_column(String)
    dataset_type: Mapped[str] = mapped_column(String)
    date: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    completeness: Mapped[str] = mapped_column(String)
    fetched_rows: Mapped[int] = mapped_column(Integer)
    aggregation_type: Mapped[str] = mapped_column(String)
    last_successful_sync_at: Mapped[str] = mapped_column(String)


class SyncJob(Base):
    __tablename__ = "gsc_sync_jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    property_id: Mapped[str] = mapped_column(ForeignKey("gsc_properties.id"))
    search_type: Mapped[str] = mapped_column(String)
    sync_mode: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    requested_date_start: Mapped[str] = mapped_column(String)
    requested_date_end: Mapped[str] = mapped_column(String)
    completed_days: Mapped[int] = mapped_column(Integer, default=0)
    total_days: Mapped[int] = mapped_column(Integer)
    rows_fetched: Mapped[int] = mapped_column(Integer, default=0)
    current_task: Mapped[str] = mapped_column(String, default="")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)


class Setting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(Text)
