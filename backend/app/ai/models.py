"""Agent-owned records only; no mutation of existing SEO facts."""

from sqlalchemy import JSON, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.models import Base


class AIConversation(Base):
    __tablename__ = "ai_conversations"
    id: Mapped[str] = mapped_column(primary_key=True)
    project_id: Mapped[str]
    title: Mapped[str]
    provider: Mapped[str]
    model: Mapped[str]
    saved: Mapped[bool]
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (Index("ix_ai_conversation_project", "project_id", "updated_at"),)


class AIMessage(Base):
    __tablename__ = "ai_messages"
    id: Mapped[str] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str]
    content: Mapped[str]
    status: Mapped[str]
    request_key: Mapped[str | None]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        Index("ix_ai_message_history", "conversation_id", "created_at"),
        Index(
            "ix_ai_active_turn",
            "conversation_id",
            unique=True,
            sqlite_where=text("role='assistant' AND status IN ('queued','running')"),
        ),
        Index(
            "ix_ai_idempotency",
            "conversation_id",
            "request_key",
            unique=True,
            sqlite_where=text("request_key IS NOT NULL"),
        ),
    )


class AIToolExecution(Base):
    __tablename__ = "ai_tool_executions"
    id: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str]
    tool_version: Mapped[str]
    input_summary: Mapped[dict] = mapped_column(JSON)
    output_summary: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str]
    duration_ms: Mapped[int]
    created_at: Mapped[str]
    __table_args__ = (Index("ix_ai_tools_message", "message_id", "created_at"),)


class AIEvidence(Base):
    __tablename__ = "ai_evidence_references"
    id: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="CASCADE")
    )
    project_id: Mapped[str]
    source_type: Mapped[str]
    source_record_id: Mapped[str | None]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    __table_args__ = (Index("ix_ai_evidence_message", "message_id"),)


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    id: Mapped[str] = mapped_column(primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("ai_conversations.id", ondelete="CASCADE")
    )
    message_id: Mapped[str] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="CASCADE")
    )
    project_id: Mapped[str]
    title: Mapped[str]
    proposed_action: Mapped[str]
    priority: Mapped[str]
    confidence: Mapped[str]
    evidence_ids: Mapped[list] = mapped_column(JSON)
    approval_status: Mapped[str]
    user_notes: Mapped[str]
    reviewed_at: Mapped[str | None]
    created_at: Mapped[str]
    updated_at: Mapped[str]
    __table_args__ = (
        Index("ix_ai_recommendation_project", "project_id", "approval_status"),
    )


class AIUsage(Base):
    __tablename__ = "ai_usage_records"
    id: Mapped[str] = mapped_column(primary_key=True)
    message_id: Mapped[str | None] = mapped_column(
        ForeignKey("ai_messages.id", ondelete="SET NULL")
    )
    provider: Mapped[str]
    model: Mapped[str]
    request_id: Mapped[str | None]
    status: Mapped[str]
    input_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    reserved_usd: Mapped[float]
    estimated_cost_usd: Mapped[float | None]
    data: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str]
    __table_args__ = (Index("ix_ai_usage_day", "created_at", "status"),)
