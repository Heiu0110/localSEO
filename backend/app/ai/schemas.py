from datetime import date, datetime
from zoneinfo import ZoneInfo
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AISettings(Input):
    enabled: bool = False
    model: str = Field(
        default="gpt-4.1-mini", pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$"
    )
    max_tool_calls: int = Field(default=6, ge=1, le=8)
    max_context_bytes: int = Field(default=48000, ge=16000, le=96000)
    max_output_tokens: int = Field(default=1600, ge=500, le=4000)
    daily_limit_usd: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)
    warning_usd: float = Field(default=0.05, ge=0, le=10, allow_inf_nan=False)
    input_usd_per_million: float | None = Field(
        default=None, ge=0, le=1000, allow_inf_nan=False
    )
    output_usd_per_million: float | None = Field(
        default=None, ge=0, le=10000, allow_inf_nan=False
    )
    pricing_reviewed_on: date | None = None

    @field_validator("model")
    @classmethod
    def model_is_not_secret(cls, value):
        if value.startswith(("sk-", "ya29.")):
            raise ValueError("Model ID không phải API key/token.")
        return value

    @model_validator(mode="after")
    def prices(self):
        if self.enabled and (
            self.input_usd_per_million is None
            or self.output_usd_per_million is None
            or self.pricing_reviewed_on is None
        ):
            raise ValueError(
                "Cần kiểm tra giá của model và cấu hình ước tính trước khi bật OpenAI."
            )
        if (
            self.pricing_reviewed_on
            and self.pricing_reviewed_on
            > datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
        ):
            raise ValueError("Ngày kiểm tra giá không thể ở tương lai.")
        return self


class ConversationCreate(Input):
    project_id: str = Field(min_length=1, max_length=150)
    title: str = Field(default="Phiên phân tích mới", min_length=1, max_length=120)
    provider: Literal["local_report", "openai"] = "local_report"


class ConversationPatch(Input):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    saved: bool | None = None


class MessageCreate(Input):
    content: str = Field(min_length=1, max_length=4000)
    days: Literal[7, 28, 90] | None = None
    end_date: date | None = None
    provider: Literal["local_report", "openai"] | None = None
    acknowledge_external_processing: bool = False
    approved_model: str | None = Field(default=None, max_length=100)
    approved_max_estimate_usd: float | None = Field(
        default=None, ge=0, le=1000, allow_inf_nan=False
    )
    request_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class Review(Input):
    approval_status: Literal[
        "proposed", "under_review", "approved", "rejected", "needs_more_evidence"
    ]
    user_notes: str = Field(default="", max_length=2000)


class Confirmation(Input):
    confirm: bool


class Finding(Input):
    title: str = Field(max_length=180)
    interpretation: str = Field(max_length=1500)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    confidence: Literal["high", "medium", "low"]
    kind: Literal["interpretation", "hypothesis"]


class Proposal(Input):
    title: str = Field(min_length=1, max_length=180)
    proposed_action: str = Field(min_length=1, max_length=2000)
    priority: Literal["high", "medium", "low"]
    confidence: Literal["high", "medium", "low"]
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class Analysis(Input):
    summary: str = Field(min_length=1, max_length=2000)
    findings: list[Finding] = Field(max_length=10)
    recommendations: list[Proposal] = Field(max_length=8)
    limitations: list[str] = Field(max_length=12)
    next_step: str = Field(max_length=1000)


class Evidence(Input):
    evidence_id: str
    project_id: str
    source_type: str
    source_name: str
    source_record_id: str | None
    metric_scope: str
    date_start: str | None
    date_end: str | None
    collected_at: str | None
    retrieved_at: str
    data_freshness: dict
    completeness: str
    value_summary: dict
    source_reference: str | None
    limitations: list[str]


class ToolEnvelope(Input):
    evidence: Evidence
