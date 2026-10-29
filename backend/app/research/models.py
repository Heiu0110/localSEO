"""Phase 7 research-owned records; no foreign-key cascade into source SEO data."""

from sqlalchemy import JSON, ForeignKey, Index, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base


class ResearchProject(Base):
    __tablename__ = "research_projects"
    id: Mapped[str] = mapped_column(primary_key=True)
    local_project_id: Mapped[str | None]
    name: Mapped[str]
    description: Mapped[str]
    business_context: Mapped[str]
    research_goal: Mapped[str]
    country: Mapped[str]
    language: Mapped[str]
    status: Mapped[str]
    settings: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (Index("ix_research_project_site", "local_project_id", "status"),)


class ResearchCluster(Base):
    __tablename__ = "research_clusters"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE")
    )
    name: Mapped[str]
    primary_keyword_id: Mapped[
        str | None
    ]  # Validated membership; avoids cyclic deletion dependencies.
    intent: Mapped[str]
    page_type: Mapped[str]
    target_url: Mapped[str]
    mapping_status: Mapped[str]
    notes: Mapped[str]
    status: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (Index("ix_research_cluster_project", "project_id", "status"),)


class ResearchKeyword(Base):
    __tablename__ = "research_keywords"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE")
    )
    keyword_text: Mapped[str]
    normalized_keyword: Mapped[str]
    country: Mapped[str]
    language: Mapped[str]
    group_name: Mapped[str]
    intent: Mapped[str]
    target_url: Mapped[str]
    mapping_status: Mapped[str]
    brand_label: Mapped[str]
    notes: Mapped[str]
    status: Mapped[str]
    cluster_id: Mapped[str | None] = mapped_column(
        ForeignKey("research_clusters.id", ondelete="SET NULL")
    )
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("project_id", "normalized_keyword", "country", "language"),
        Index(
            "ix_research_keyword_lookup", "project_id", "status", "normalized_keyword"
        ),
        Index("ix_research_members", "cluster_id"),
    )


class ResearchSource(Base):
    __tablename__ = "research_keyword_sources"
    id: Mapped[str] = mapped_column(primary_key=True)
    keyword_id: Mapped[str] = mapped_column(
        ForeignKey("research_keywords.id", ondelete="CASCADE")
    )
    identity: Mapped[str]
    provider: Mapped[str]
    method: Mapped[str]
    reference: Mapped[str]
    original_text: Mapped[str]
    seed: Mapped[str]
    collected_at: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint("keyword_id", "identity"),)


class ResearchMetric(Base):
    __tablename__ = "research_keyword_metrics"
    id: Mapped[str] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(
        ForeignKey("research_keyword_sources.id", ondelete="CASCADE")
    )
    metric_type: Mapped[str]
    value: Mapped[float]
    unit: Mapped[str]
    scope: Mapped[str]
    reporting_start: Mapped[str | None]
    reporting_end: Mapped[str | None]
    metadata_json: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("source_id", "metric_type"),
        CheckConstraint("value >= 0"),
    )


class SerpSnapshot(Base):
    __tablename__ = "research_serp_snapshots"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE")
    )
    keyword_id: Mapped[str] = mapped_column(
        ForeignKey("research_keywords.id", ondelete="CASCADE")
    )
    identity: Mapped[str]
    provider: Mapped[str]
    search_engine: Mapped[str]
    search_type: Mapped[str]
    country: Mapped[str]
    language: Mapped[str]
    location: Mapped[str]
    device: Mapped[str]
    requested_depth: Mapped[int]
    returned_depth: Mapped[int]
    collected_at: Mapped[str]
    completeness: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("project_id", "identity"),
        Index("ix_research_serp_lookup", "project_id", "keyword_id", "collected_at"),
    )


class SerpResult(Base):
    __tablename__ = "research_serp_results"
    id: Mapped[str] = mapped_column(primary_key=True)
    snapshot_id: Mapped[str] = mapped_column(
        ForeignKey("research_serp_snapshots.id", ondelete="CASCADE")
    )
    organic_position: Mapped[int | None]
    provider_position: Mapped[str]
    result_type: Mapped[str]
    title: Mapped[str]
    url: Mapped[str]
    normalized_url: Mapped[str]
    domain: Mapped[str]
    snippet: Mapped[str]
    features: Mapped[list] = mapped_column(JSON)
    __table_args__ = (
        Index("ix_research_serp_results", "snapshot_id", "organic_position"),
    )


class ResearchOpportunity(Base):
    __tablename__ = "research_opportunities"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE")
    )
    keyword_id: Mapped[str] = mapped_column(
        ForeignKey("research_keywords.id", ondelete="CASCADE")
    )
    kind: Mapped[str]
    priority: Mapped[str]
    confidence: Mapped[str]
    proposed_action: Mapped[str]
    evidence: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str]
    notes: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("keyword_id", "kind"),
        Index("ix_research_opportunities", "project_id", "status"),
    )


class ResearchReview(Base):
    __tablename__ = "research_review_events"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE")
    )
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    decision: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class ResearchJob(Base):
    __tablename__ = "research_import_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("research_projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str]
    status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
