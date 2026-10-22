from sqlalchemy import Boolean, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class AuditProject(Base):
    __tablename__ = "technical_projects"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    root_url: Mapped[str] = mapped_column(Text)
    property_id: Mapped[str | None] = mapped_column(ForeignKey("gsc_properties.id"), nullable=True)
    source_type: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class AuditRun(Base):
    __tablename__ = "technical_audits"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("technical_projects.id"))
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String)
    config: Mapped[dict] = mapped_column(JSON)
    scope_hash: Mapped[str] = mapped_column(String)
    rule_version: Mapped[str] = mapped_column(String)
    phase: Mapped[str] = mapped_column(Text)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    requests: Mapped[int] = mapped_column(Integer, default=0)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    coverage: Mapped[dict] = mapped_column(JSON)
    summary: Mapped[dict] = mapped_column(JSON)
    started_at: Mapped[str] = mapped_column(String)
    finished_at: Mapped[str | None] = mapped_column(String, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditURL(Base):
    __tablename__ = "technical_urls"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("technical_audits.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    original_url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, default="")
    indexability: Mapped[str] = mapped_column(String, default="unknown")
    inbound: Mapped[int] = mapped_column(Integer, default=0)
    outbound: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    sources: Mapped[list] = mapped_column(JSON)
    data: Mapped[dict] = mapped_column(JSON)
    crawled_at: Mapped[str | None] = mapped_column(String, nullable=True)


class AuditLink(Base):
    __tablename__ = "technical_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("technical_audits.id", ondelete="CASCADE"))
    source_id: Mapped[str] = mapped_column(ForeignKey("technical_urls.id", ondelete="CASCADE"))
    target_url: Mapped[str] = mapped_column(Text)
    anchor: Mapped[str] = mapped_column(Text)
    rel: Mapped[str] = mapped_column(String)
    context: Mapped[str] = mapped_column(String)
    internal: Mapped[bool] = mapped_column(Boolean)


class AuditSitemap(Base):
    __tablename__ = "technical_sitemaps"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("technical_audits.id", ondelete="CASCADE"))
    url: Mapped[str] = mapped_column(Text)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data: Mapped[dict] = mapped_column(JSON)


class AuditIssue(Base):
    __tablename__ = "technical_issues"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    audit_id: Mapped[str] = mapped_column(ForeignKey("technical_audits.id", ondelete="CASCADE"))
    project_id: Mapped[str] = mapped_column(ForeignKey("technical_projects.id"))
    url_id: Mapped[str | None] = mapped_column(ForeignKey("technical_urls.id", ondelete="CASCADE"), nullable=True)
    fingerprint: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(Text)
    rule_id: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    confidence: Mapped[str] = mapped_column(String)
    evidence_type: Mapped[str] = mapped_column(String)
    evidence: Mapped[dict] = mapped_column(JSON)
    recommendation: Mapped[str] = mapped_column(Text)
    verification: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer)
    priority_reasons: Mapped[list] = mapped_column(JSON)
    first_seen_at: Mapped[str] = mapped_column(String)
    last_seen_at: Mapped[str] = mapped_column(String)


class AuditTask(Base):
    __tablename__ = "technical_tasks"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("technical_projects.id"))
    fingerprint: Mapped[str] = mapped_column(String)
    rule_id: Mapped[str] = mapped_column(String)
    url: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    owner: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    verification: Mapped[str] = mapped_column(String)
    verification_audit_id: Mapped[str | None] = mapped_column(String, nullable=True)
    priority: Mapped[int] = mapped_column(Integer)
    first_seen_at: Mapped[str] = mapped_column(String)
    last_seen_at: Mapped[str] = mapped_column(String)


class URLIntent(Base):
    __tablename__ = "technical_url_intents"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("technical_projects.id"))
    url: Mapped[str] = mapped_column(Text)
    importance: Mapped[str] = mapped_column(String)
    should_index: Mapped[str] = mapped_column(String)
    page_type: Mapped[str] = mapped_column(Text)
    notes: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)


class AuditImport(Base):
    __tablename__ = "technical_imports"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("technical_projects.id"))
    filename: Mapped[str] = mapped_column(Text)
    digest: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    rows: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[str] = mapped_column(String)
