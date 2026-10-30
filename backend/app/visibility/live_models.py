"""Additive collection audit records; monetary usage stays in the existing AI ledger."""

from sqlalchemy import ForeignKey, Index, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base


class CollectionRequest(Base):
    __tablename__ = "visibility_collection_requests"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("visibility_projects.id"))
    prompt_id: Mapped[str] = mapped_column(ForeignKey("visibility_prompts.id"))
    request_key: Mapped[str]
    status: Mapped[str]
    active_slot: Mapped[int | None] = mapped_column(nullable=True, unique=True)
    binding_hash: Mapped[str]
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("visibility_observations.id"), nullable=True
    )
    usage_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_usage_records.id"), nullable=True
    )
    dispatched_at: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("project_id", "request_key"),
        Index("ix_visibility_collection_project", "project_id", "created_at"),
    )


class CollectionConsent(Base):
    __tablename__ = "visibility_collection_consents"
    id: Mapped[str] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_collection_requests.id"), unique=True
    )
    binding_hash: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class SearchSource(Base):
    __tablename__ = "visibility_search_sources"
    id: Mapped[str] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_collection_requests.id")
    )
    observation_id: Mapped[str | None] = mapped_column(
        ForeignKey("visibility_observations.id"), nullable=True
    )
    project_id: Mapped[str] = mapped_column(ForeignKey("visibility_projects.id"))
    normalized_url: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        Index("ix_visibility_search_sources", "project_id", "observation_id"),
    )
