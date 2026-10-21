from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SearchType = Literal["web", "image", "video", "news"]
Dataset = Literal["site", "page", "query", "country", "device"]
SourceType = Literal["mock", "gsc", "fixture"]


class PropertyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    connection_id: str
    site_url: str
    display_name: str
    property_type: str
    permission_level: str
    source_type: str
    is_active: bool
    added_at: str
    last_synced_at: str | None
    local_start: str | None = None
    local_end: str | None = None
    sync_status: str = "not_started"


class IntegrationStatus(BaseModel):
    status: str
    configured: bool
    secure_storage_available: bool
    connection_id: str | None = None
    display_name: str | None = None
    message: str | None = None
    scope: str
    latest_final_date: date
    history_start: date
    pending_authorization: bool = False


class PropertySelection(BaseModel):
    property_id: str
    is_active: bool


class DisconnectRequest(BaseModel):
    revoke: bool = True


class DisconnectResult(BaseModel):
    local_credentials_removed: bool
    remote_revoked: bool
    message: str


class SyncRequest(BaseModel):
    property_id: str
    start_date: date
    end_date: date
    search_type: SearchType = "web"
    sync_mode: Literal["initial", "incremental", "refresh", "resume"] = "initial"

    @model_validator(mode="after")
    def validate_range(self):
        if self.end_date < self.start_date:
            raise ValueError("Ngày kết thúc phải sau ngày bắt đầu.")
        if (self.end_date - self.start_date).days > 500:
            raise ValueError("Mỗi lần đồng bộ tối đa 501 ngày.")
        return self


class JobView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    property_id: str
    search_type: str
    sync_mode: str
    status: str
    requested_date_start: str
    requested_date_end: str
    completed_days: int
    total_days: int
    rows_fetched: int
    current_task: str
    retry_count: int
    cancel_requested: bool
    started_at: str
    updated_at: str
    finished_at: str | None
    error_code: str | None
    error_message: str | None


class Coverage(BaseModel):
    expected_days: int
    synchronized_days: int
    available_days: int
    empty_days: int
    completeness: Literal["api_response", "api_limited", "unknown"]
    aggregation_type: str


class CoverageReport(BaseModel):
    current: Coverage
    previous: Coverage
    comparison_available: bool
    warnings: list[str] = Field(default_factory=list)
