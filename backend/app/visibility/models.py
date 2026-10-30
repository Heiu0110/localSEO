"""Additive Phase 8 records. Original observations and extraction revisions are immutable."""

from sqlalchemy import ForeignKey, Index, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base


class VisibilityProject(Base):
    __tablename__ = "visibility_projects"
    id: Mapped[str] = mapped_column(primary_key=True)
    local_project_id: Mapped[str]
    name: Mapped[str]
    country: Mapped[str]
    language: Mapped[str]
    description: Mapped[str]
    research_goal: Mapped[str]
    status: Mapped[str]
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (Index("ix_visibility_site", "local_project_id", "status"),)


class VisibilityEntity(Base):
    __tablename__ = "visibility_entities"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str]
    name: Mapped[str]
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (UniqueConstraint("project_id", "kind", "name"),)


class VisibilityPrompt(Base):
    __tablename__ = "visibility_prompts"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    text: Mapped[str]
    identity: Mapped[str]
    category: Mapped[str]
    intent: Mapped[str]
    cohort_type: Mapped[str]
    priority: Mapped[int]
    status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("project_id", "identity"),
        Index("ix_visibility_prompt", "project_id", "status", "category"),
    )


class VisibilityObservation(Base):
    __tablename__ = "visibility_observations"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    prompt_id: Mapped[str] = mapped_column(ForeignKey("visibility_prompts.id"))
    identity: Mapped[str]
    provider: Mapped[str]
    model: Mapped[str | None]
    collection_method: Mapped[str]
    prompt_snapshot: Mapped[str]
    response_text: Mapped[str]
    observed_at: Mapped[str | None]
    imported_at: Mapped[str]
    completeness: Mapped[str]
    citation_capability: Mapped[str]
    citation_metadata: Mapped[str]
    supersedes_id: Mapped[str | None] = mapped_column(
        ForeignKey("visibility_observations.id")
    )
    original: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        UniqueConstraint("project_id", "identity"),
        UniqueConstraint("supersedes_id"),
        Index(
            "ix_visibility_observation",
            "project_id",
            "provider",
            "model",
            "observed_at",
        ),
        Index("ix_visibility_observation_prompt", "prompt_id"),
    )


class VisibilityExtraction(Base):
    __tablename__ = "visibility_extractions"
    id: Mapped[str] = mapped_column(primary_key=True)
    observation_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_observations.id", ondelete="CASCADE")
    )
    revision: Mapped[int]
    registry_hash: Mapped[str]
    config_snapshot: Mapped[list] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    __table_args__ = (UniqueConstraint("observation_id", "revision"),)


class VisibilityMention(Base):
    __tablename__ = "visibility_mentions"
    id: Mapped[str] = mapped_column(primary_key=True)
    extraction_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_extractions.id", ondelete="CASCADE")
    )
    entity_id: Mapped[str] = mapped_column(ForeignKey("visibility_entities.id"))
    start: Mapped[int]
    end: Mapped[int]
    matched_text: Mapped[str]
    alias: Mapped[str]
    detected_status: Mapped[str]
    status: Mapped[str]
    reason: Mapped[str]
    __table_args__ = (Index("ix_visibility_entity_mention", "entity_id", "status"),)


class VisibilityCitation(Base):
    __tablename__ = "visibility_citations"
    id: Mapped[str] = mapped_column(primary_key=True)
    extraction_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_extractions.id", ondelete="CASCADE")
    )
    entity_id: Mapped[str | None] = mapped_column(ForeignKey("visibility_entities.id"))
    raw_url: Mapped[str]
    normalized_url: Mapped[str]
    domain: Mapped[str]
    source_type: Mapped[str]
    ownership: Mapped[str]
    attribution_status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (
        Index("ix_visibility_citation_domain", "domain"),
        Index("ix_visibility_citation_entity", "entity_id", "ownership"),
    )


class VisibilityDocument(Base):
    __tablename__ = "visibility_documents"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str]
    url: Mapped[str]
    content: Mapped[str]
    approved: Mapped[bool]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class VisibilityCoverage(Base):
    __tablename__ = "visibility_coverage_reviews"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    requirement_id: Mapped[str] = mapped_column(ForeignKey("visibility_documents.id"))
    page_id: Mapped[str] = mapped_column(ForeignKey("visibility_documents.id"))
    decision: Mapped[str]
    reason: Mapped[str]
    created_at: Mapped[str]


class VisibilityEvidence(Base):
    __tablename__ = "visibility_evidence"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    source_type: Mapped[str]
    source_id: Mapped[str]
    signature: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("project_id", "source_type", "source_id", "signature"),
    )


class VisibilityOpportunity(Base):
    __tablename__ = "visibility_opportunities"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    identity: Mapped[str]
    rule_id: Mapped[str]
    title: Mapped[str]
    category: Mapped[str]
    priority: Mapped[str]
    review_status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        UniqueConstraint("project_id", "identity"),
        Index("ix_visibility_opportunity", "project_id", "review_status", "rule_id"),
    )


class VisibilityReview(Base):
    __tablename__ = "visibility_reviews"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    decision: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class VisibilityImportJob(Base):
    __tablename__ = "visibility_import_jobs"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    kind: Mapped[str]
    identity: Mapped[str]
    status: Mapped[str]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    __table_args__ = (UniqueConstraint("project_id", "kind", "identity"),)


class VisibilityRun(Base):
    __tablename__ = "visibility_detection_runs"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    scope: Mapped[dict] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]


class VisibilityAgentAnalysis(Base):
    __tablename__ = "visibility_agent_analyses"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_projects.id", ondelete="CASCADE")
    )
    opportunity_id: Mapped[str] = mapped_column(
        ForeignKey("visibility_opportunities.id", ondelete="CASCADE")
    )
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="SET NULL")
    )
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
