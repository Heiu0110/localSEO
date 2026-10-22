from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CrawlConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["quick", "standard", "advanced"] = "quick"
    max_urls: int = Field(100, ge=1, le=5000)
    delay_seconds: float = Field(1, ge=0.5, le=10, allow_inf_nan=False)
    max_depth: int = Field(8, ge=0, le=30)
    timeout_seconds: float = Field(15, ge=2, le=60, allow_inf_nan=False)
    allowed_hosts: list[str] = Field(default_factory=list, max_length=5)
    include_patterns: list[str] = Field(default_factory=list, max_length=10)
    exclude_patterns: list[str] = Field(default_factory=list, max_length=10)
    query_policy: Literal["preserve", "drop_tracking", "drop_all"] = "preserve"
    follow_redirects: bool = True
    sitemap_urls: list[str] = Field(default_factory=list, max_length=5)
    important_urls: list[str] = Field(default_factory=list, max_length=100)
    use_gsc: bool = True
    user_agent: str = Field("LocalSEOWorkspace/0.3 (+read-only technical audit)", min_length=20, max_length=200)


class ProjectInput(BaseModel):
    name: str = Field("", max_length=150)
    root_url: str = Field(max_length=2048)
    property_id: str | None = None
    config: CrawlConfig = Field(default_factory=CrawlConfig)


class AuditInput(BaseModel):
    project_id: str
    name: str = Field("", max_length=150)
    config: CrawlConfig | None = None


class ProjectView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    root_url: str
    property_id: str | None
    source_type: str
    config: dict
    created_at: str
    updated_at: str


class AuditView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    project_id: str
    name: str
    status: str
    phase: str
    processed: int
    requests: int
    config: dict
    coverage: dict
    summary: dict
    started_at: str
    finished_at: str | None
    error: str | None


class TaskUpdate(BaseModel):
    status: Literal["open", "in_progress", "fixed", "ignored", "resolved"]
    owner: str = Field("", max_length=100)
    notes: str = Field("", max_length=4000)


class IntentInput(BaseModel):
    url: str = Field(max_length=2048)
    importance: Literal["critical_money", "important", "supporting", "low"] = "supporting"
    should_index: Literal["yes", "no", "undecided"] = "undecided"
    page_type: str = Field("", max_length=100)
    notes: str = Field("", max_length=2000)


class PageResult(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    page: int
    page_size: int


class ConfirmDelete(BaseModel):
    confirm: bool = False
