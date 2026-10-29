"""Public output contracts retain bounded metadata, without accepting secret fields as commands."""

from pydantic import BaseModel, ConfigDict, Field
from .schemas import Intent, Status, Mapping, MetricInput


class Output(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProjectOutput(Output):
    id: str
    local_project_id: str | None
    name: str
    country: str
    language: str
    keyword_count: int = Field(ge=0)
    snapshot_count: int = Field(ge=0)
    settings: dict[str, float]


class SourceOutput(Output):
    id: str
    provider: str
    method: str
    reference: str
    collected_at: str
    metrics: list[MetricInput] = Field(max_length=10)


class KeywordOutput(Output):
    id: str
    project_id: str
    keyword_text: str
    country: str
    language: str
    intent: Intent
    status: Status
    mapping_status: Mapping
    sources: list[SourceOutput] = Field(default_factory=list, max_length=100)


class KeywordPageOutput(Output):
    rows: list[KeywordOutput] = Field(max_length=100)
    total: int = Field(ge=0)
    page: int = Field(ge=1)


class JobOutput(Output):
    id: str
    project_id: str
    kind: str
    status: str
    data: dict


class ClusterOutput(Output):
    id: str
    name: str
    status: Status
    keyword_count: int = Field(ge=0)
    keywords: list[KeywordOutput] = Field(max_length=500)
