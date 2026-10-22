from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SetCreate(Input):
    site_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    start_date: date
    timezone: str = "Asia/Ho_Chi_Minh"

    @field_validator("timezone")
    @classmethod
    def zone(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Múi giờ không hợp lệ.")
        return value


class SetPatch(Input):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["active", "archived"] | None = None
    start_date: date | None = None
    timezone: str | None = None
    min_impressions: int | None = Field(default=None, ge=1, le=10000000)
    low_ctr: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    _zone = field_validator("timezone")(lambda v: SetCreate.zone(v) if v else v)


class KeywordInput(Input):
    keyword_set_id: str
    keyword_text: str = Field(min_length=1, max_length=500)
    group_id: str | None = None
    target_url: str = Field(default="", max_length=2048)
    match_mode: Literal["exact_url", "domain"] | None = None
    priority: Literal["high", "normal", "low"] = "normal"
    search_intent: str = Field(default="", max_length=100)
    status: Literal["active", "paused", "archived"] = "active"
    notes: str = Field(default="", max_length=4000)


class KeywordPatch(Input):
    keyword_text: str | None = Field(default=None, min_length=1, max_length=500)
    keyword_set_id: str | None = None
    group_id: str | None = None
    target_url: str | None = Field(default=None, max_length=2048)
    match_mode: Literal["exact_url", "domain"] | None = None
    priority: Literal["high", "normal", "low"] | None = None
    search_intent: str | None = Field(default=None, max_length=100)
    status: Literal["active", "paused", "archived"] | None = None
    notes: str | None = Field(default=None, max_length=4000)


class GroupInput(Input):
    keyword_set_id: str
    name: str = Field(min_length=1, max_length=100)
    color: str = Field(default="#946447", pattern=r"^#[0-9a-fA-F]{6}$")
    sort_order: int = Field(default=0, ge=0, le=10000)


class ProfileInput(Input):
    keyword_set_id: str
    name: str = Field(default="Google Việt Nam · Desktop", min_length=1, max_length=100)
    search_engine: Literal["Google"] = "Google"
    country: str = Field(default="VN", pattern=r"^[A-Z]{2}$")
    language: str = Field(default="vi", pattern=r"^[a-z]{2,3}(-[A-Z]{2})?$")
    location_label: str = Field(default="Việt Nam", max_length=200)
    device: Literal["desktop", "mobile", "tablet"] = "desktop"
    search_depth: int = Field(default=100, ge=1, le=1000)
    result_type: Literal["organic_web"] = "organic_web"


class RankInput(Input):
    keyword_id: str
    week_number: int = Field(ge=1, le=520)
    profile_id: str
    value: str = Field(max_length=8)
    checked_at: datetime | None = None
    timestamp_precision: Literal["exact", "week_only"] = "exact"
    checked_by: str = Field(default="Người dùng cục bộ", max_length=100)
    matched_url: str = Field(default="", max_length=2048)
    notes: str = Field(default="", max_length=4000)


class RankBulk(Input):
    rows: list[RankInput] = Field(min_length=1, max_length=500)


class KeywordBulk(Input):
    ids: list[str] = Field(min_length=1, max_length=200)
    changes: KeywordPatch


class SyncInput(Input):
    keyword_set_id: str
    date_start: date
    date_end: date
    scope: Literal["property", "page"] = "property"
    refresh: bool = False


class Confirmation(Input):
    confirm: bool
