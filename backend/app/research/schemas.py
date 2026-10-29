from datetime import date, datetime, timezone, timedelta
from typing import Literal
from pydantic import Field, model_validator, field_validator
from app.ai.schemas import Input
from app.keywords.core import safe_url, normalize

Status = Literal["draft", "needs_review", "approved", "rejected", "archived"]
Intent = Literal[
    "unknown",
    "informational",
    "commercial",
    "transactional",
    "navigational",
    "local",
    "mixed",
]
Mapping = Literal["undecided", "suggested", "approved", "planned"]


class ProjectInput(Input):
    local_project_id: str | None = Field(default=None, max_length=150)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    business_context: str = Field(default="", max_length=2000)
    research_goal: str = Field(default="", max_length=2000)
    country: str = Field(default="VN", pattern=r"^[A-Z]{2}$")
    language: str = Field(default="vi", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")


class ProjectPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    business_context: str | None = Field(default=None, max_length=2000)
    research_goal: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "archived"] | None = None
    min_impressions: int | None = Field(default=None, ge=10, le=10000000)
    low_ctr: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    near_min: float | None = Field(default=None, ge=1, le=100, allow_inf_nan=False)
    near_max: float | None = Field(default=None, ge=1, le=100, allow_inf_nan=False)


class MetricInput(Input):
    metric_type: Literal[
        "gsc_clicks",
        "gsc_impressions",
        "gsc_ctr",
        "gsc_position",
        "search_volume",
        "cpc",
        "paid_competition",
        "organic_difficulty",
        "relative_interest",
    ]
    value: float = Field(ge=0, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=100)
    scope: str = Field(min_length=1, max_length=200)
    reporting_start: date | None = None
    reporting_end: date | None = None
    metadata: dict[str, str] = Field(default_factory=dict, max_length=10)

    @model_validator(mode="after")
    def valid(self):
        expected = {
            "gsc_clicks": "clicks",
            "gsc_impressions": "impressions",
            "gsc_ctr": "ratio",
            "gsc_position": "average_position",
            "search_volume": "searches/month",
            "relative_interest": "index_0_100",
        }
        if self.metric_type in expected and self.unit != expected[self.metric_type]:
            raise ValueError("Đơn vị không đúng với metric.")
        if self.metric_type == "gsc_ctr" and self.value > 1:
            raise ValueError("CTR cần là tỷ lệ 0–1.")
        if self.metric_type.startswith("gsc_") and (
            not self.reporting_start or not self.reporting_end
        ):
            raise ValueError("GSC metric cần kỳ báo cáo.")
        if self.metric_type == "cpc" and not self.unit.startswith("currency/"):
            raise ValueError("CPC cần currency/USD hoặc currency/VND.")
        if (
            self.reporting_start
            and self.reporting_end
            and self.reporting_start > self.reporting_end
        ):
            raise ValueError("Kỳ báo cáo không hợp lệ.")
        if self.metric_type in (
            "paid_competition",
            "organic_difficulty",
        ) and not self.metadata.get("scale"):
            raise ValueError("Cần ghi thang đo của provider.")
        if self.metric_type == "relative_interest" and self.value > 100:
            raise ValueError("Relative interest tối đa 100.")
        if any(len(k) > 100 or len(v) > 1000 for k, v in self.metadata.items()):
            raise ValueError("Metadata quá dài.")
        return self


class Candidate(Input):
    keyword_text: str = Field(min_length=1, max_length=500)
    country: str = Field(default="VN", pattern=r"^[A-Z]{2}$")
    language: str = Field(default="vi", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    provider: str = Field(default="user_supplied", min_length=1, max_length=100)
    method: str = Field(default="seed", max_length=100)
    reference: str = Field(default="", max_length=2000)
    seed: str = Field(default="", max_length=500)
    collected_at: datetime | None = None
    group_name: str = Field(default="", max_length=100)
    intent: Intent = "unknown"
    target_url: str = Field(default="", max_length=2048)
    notes: str = Field(default="", max_length=4000)
    metrics: list[MetricInput] = Field(default_factory=list, max_length=10)
    metadata: dict[str, str] = Field(default_factory=dict, max_length=10)
    _url = field_validator("target_url")(safe_url)

    @model_validator(mode="after")
    def consistent_observation(self):
        types = [m.metric_type for m in self.metrics]
        if len(types) != len(set(types)):
            raise ValueError("Metric type bị trùng trong cùng observation.")
        periods = {
            (m.reporting_start, m.reporting_end, m.scope)
            for m in self.metrics
            if m.metric_type.startswith("gsc_")
        }
        if len(periods) > 1:
            raise ValueError("GSC metrics trong observation cần cùng scope/kỳ.")
        if self.collected_at and (
            not self.collected_at.tzinfo
            or self.collected_at > datetime.now(timezone.utc) + timedelta(minutes=5)
        ):
            raise ValueError("Thời gian nguồn cần timezone và không ở tương lai.")
        return self

    @field_validator("keyword_text")
    @classmethod
    def nonempty(cls, v):
        if not normalize(v) or any(ord(c) < 32 and not c.isspace() for c in v):
            raise ValueError("Từ khóa rỗng/không hợp lệ.")
        return v


class Discovery(Input):
    source: Literal["seed", "gsc", "tracking", "crawl", "rows"]
    text: str = Field(default="", max_length=50000)
    rows: list[Candidate] = Field(default_factory=list, max_length=1000)
    set_id: str | None = Field(default=None, max_length=100)
    group_id: str | None = Field(default=None, max_length=100)
    days: Literal[7, 28, 90] = 28
    end_date: date | None = None
    search: str = Field(default="", max_length=200)
    min_impressions: int = Field(default=0, ge=0)
    min_clicks: int = Field(default=0, ge=0)
    max_ctr: float = Field(default=1, ge=0, le=1, allow_inf_nan=False)
    min_position: float = Field(default=0, ge=0, allow_inf_nan=False)
    max_position: float = Field(default=1000, ge=0, allow_inf_nan=False)
    limit: int = Field(default=200, ge=1, le=1000)


class Confirm(Input):
    confirm: bool


class KeywordPatch(Input):
    group_name: str | None = Field(default=None, max_length=100)
    intent: Intent | None = None
    target_url: str | None = Field(default=None, max_length=2048)
    mapping_status: Mapping | None = None
    brand_label: Literal["unknown", "branded", "non_branded"] | None = None
    notes: str | None = Field(default=None, max_length=4000)
    status: Status | None = None
    cluster_id: str | None = Field(default=None, max_length=100)
    _url = field_validator("target_url")(lambda v: safe_url(v) if v is not None else v)


class Bulk(Input):
    ids: list[str] = Field(min_length=1, max_length=200)
    changes: KeywordPatch


class ClusterInput(Input):
    name: str = Field(min_length=1, max_length=200)
    keyword_ids: list[str] = Field(default_factory=list, max_length=200)
    primary_keyword_id: str | None = Field(default=None, max_length=100)
    intent: Intent = "unknown"
    page_type: str = Field(default="", max_length=100)
    target_url: str = Field(default="", max_length=2048)
    mapping_status: Mapping = "undecided"
    notes: str = Field(default="", max_length=2000)
    _url = field_validator("target_url")(safe_url)


class ClusterPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    primary_keyword_id: str | None = Field(default=None, max_length=100)
    intent: Intent | None = None
    page_type: str | None = Field(default=None, max_length=100)
    target_url: str | None = Field(default=None, max_length=2048)
    mapping_status: Mapping | None = None
    notes: str | None = Field(default=None, max_length=2000)
    status: Status | None = None
    _url = field_validator("target_url")(lambda v: safe_url(v) if v is not None else v)


class ClusterOperation(Input):
    operation: Literal["delete", "merge", "split", "assign"]
    keyword_ids: list[str] = Field(default_factory=list, max_length=200)
    destination_id: str | None = Field(default=None, max_length=100)
    name: str = Field(default="Nhóm tách", min_length=1, max_length=200)
    confirm: bool = False


class Suggest(Input):
    method: Literal["lexical", "serp_overlap"] = "lexical"


class SerpRow(Input):
    organic_position: int | None = Field(default=None, ge=1, le=100)
    provider_position: str = Field(default="", max_length=100)
    result_type: Literal["organic", "paid", "feature"] = "organic"
    title: str = Field(default="", max_length=1000)
    url: str = Field(min_length=1, max_length=2048)
    snippet: str = Field(default="", max_length=2000)
    features: list[str] = Field(default_factory=list, max_length=10)
    _url = field_validator("url")(safe_url)

    @model_validator(mode="after")
    def positions(self):
        if self.result_type == "organic" and self.organic_position is None:
            raise ValueError("Organic cần vị trí quan sát.")
        if self.result_type != "organic" and self.organic_position is not None:
            raise ValueError("Không trộn quảng cáo/feature vào organic position.")
        if any(len(x) > 100 for x in self.features):
            raise ValueError("Feature quá dài.")
        return self


class SerpInput(Input):
    keyword_id: str = Field(min_length=1, max_length=100)
    provider: str = Field(min_length=1, max_length=100)
    search_engine: Literal["Google", "Bing", "Other"] = "Google"
    search_type: Literal["web"] = "web"
    country: str = Field(default="VN", pattern=r"^[A-Z]{2}$")
    language: str = Field(default="vi", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    location: str = Field(min_length=1, max_length=200)
    device: Literal["desktop", "mobile", "tablet"] = "desktop"
    requested_depth: int = Field(default=10, ge=1, le=100)
    collected_at: datetime
    completeness: Literal["complete_observed", "partial", "unknown"] = "unknown"
    request_id: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=2000)
    results: list[SerpRow] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def valid(self):
        if not self.collected_at.tzinfo or self.collected_at > datetime.now(
            timezone.utc
        ) + timedelta(minutes=5):
            raise ValueError("Snapshot cần thời điểm có múi giờ, không ở tương lai.")
        organic = [
            r.organic_position for r in self.results if r.result_type == "organic"
        ]
        if len(organic) != len(set(organic)) or any(
            x > self.requested_depth for x in organic
        ):
            raise ValueError("Vị trí organic trùng/vượt độ sâu.")
        if self.completeness == "complete_observed" and set(organic) != set(
            range(1, self.requested_depth + 1)
        ):
            raise ValueError("Complete cần đủ các vị trí Top N được khai báo.")
        return self


class Transfer(Input):
    keyword_ids: list[str] = Field(min_length=1, max_length=200)
    set_id: str = Field(min_length=1, max_length=100)
    group_id: str | None = Field(default=None, max_length=100)


class Review(Input):
    status: Status
    notes: str = Field(default="", max_length=2000)
