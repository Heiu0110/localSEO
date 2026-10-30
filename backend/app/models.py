from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Site(BaseModel):
    id: str
    domain: str
    source_type: Literal["mock", "gsc", "fixture"] = "mock"


class Metrics(BaseModel):
    clicks: int = Field(ge=0)
    impressions: int = Field(ge=0)
    ctr: float = Field(ge=0, le=100, description="Clicks / impressions × 100")
    position: float = Field(ge=0, description="Impression-weighted average position")


class Period(BaseModel):
    start: date
    end: date
    days: int


class Change(BaseModel):
    delta: float | None
    percent: float | None = None


class Changes(BaseModel):
    clicks: Change
    impressions: Change
    ctr: Change
    position: Change


class Overview(BaseModel):
    site_id: str
    period: Period
    previous_period: Period
    current: Metrics
    previous: Metrics
    changes: Changes
    source: Literal["mock", "gsc", "fixture"] = "mock"
    last_updated: datetime
    dataset_start: date
    dataset_end: date
    has_data: bool = True
    comparison_available: bool = True
    coverage: dict | None = None
    last_synced_at: str | None = None
    warnings: list[str] = Field(default_factory=list)


class PerformancePoint(BaseModel):
    date: date
    metrics: Metrics | None
    previous_date: date
    previous_metrics: Metrics | None


class Performance(BaseModel):
    site_id: str
    period: Period
    points: list[PerformancePoint]


class DimensionRow(BaseModel):
    id: str
    label: str
    metrics: Metrics
    previous: Metrics
    click_change_pct: float | None
    impression_change_pct: float | None = None
    share: float | None = None
    current_available: bool = True
    previous_available: bool = True
    code: str | None = None


class DimensionReport(BaseModel):
    site_id: str
    period: Period
    coverage: Literal["complete", "partial", "unknown"] = "complete"
    rows: list[DimensionRow]
    total_rows: int | None = None
    warning: str | None = None
    page: int = 1
    page_size: int = 100
    completeness: Literal["complete", "api_response", "api_limited", "unknown"] = "complete"


class CountryRow(BaseModel):
    code: str
    name: str
    metrics: Metrics
    share: float = Field(ge=0, le=100, description="Share of clicks, percent")
    current_available: bool = True


class CountryReport(BaseModel):
    site_id: str
    period: Period
    rows: list[CountryRow]
    coverage: Literal["complete", "partial"] = "complete"
    share_basis: Literal["site", "returned_rows"] = "site"


class PageDetail(BaseModel):
    id: str
    url: str
    period: Period
    current: Metrics
    previous: Metrics
    performance: list[PerformancePoint]
    queries: list[DimensionRow]
    source: Literal["mock", "gsc", "fixture"] = "mock"
    query_relationships_available: bool = True
    has_data: bool = True
    comparison_available: bool = True


class DataSource(BaseModel):
    id: str
    name: str
    status: Literal["Mock Mode", "Not Connected", "Planned", "Not Configured", "Connected", "Syncing", "Up to Date", "Stale", "Reauthorization Required", "Error", "Fixture", "Not Audited", "Auditing", "Audited", "Partial"]
    detail: str


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    provider: Literal["hybrid"] = "hybrid"
    version: str = "0.8.0"
