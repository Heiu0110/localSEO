from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Site(BaseModel):
    id: str
    domain: str


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
    delta: float
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
    source: Literal["mock"] = "mock"
    last_updated: datetime
    dataset_start: date
    dataset_end: date


class PerformancePoint(BaseModel):
    date: date
    metrics: Metrics
    previous_date: date
    previous_metrics: Metrics


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


class DimensionReport(BaseModel):
    site_id: str
    period: Period
    coverage: Literal["complete"] = "complete"
    rows: list[DimensionRow]


class CountryRow(BaseModel):
    code: str
    name: str
    metrics: Metrics
    share: float = Field(ge=0, le=100, description="Share of clicks, percent")


class CountryReport(BaseModel):
    site_id: str
    period: Period
    rows: list[CountryRow]


class PageDetail(BaseModel):
    id: str
    url: str
    period: Period
    current: Metrics
    previous: Metrics
    performance: list[PerformancePoint]
    queries: list[DimensionRow]


class DataSource(BaseModel):
    id: str
    name: str
    status: Literal["Mock Mode", "Not Connected", "Planned", "Not Configured"]
    detail: str


class Health(BaseModel):
    status: Literal["ok"] = "ok"
    provider: Literal["mock"] = "mock"
    version: str = "0.1.0"
