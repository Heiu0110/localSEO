import json
import random
import time
from datetime import date
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Protocol

import google_auth_httplib2
import httplib2
from google.auth.exceptions import RefreshError, TransportError
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.gsc.errors import GSCError

DIMENSIONS = {"site": [], "page": ["page"], "query": ["query"], "country": ["country"], "device": ["device"]}


class GSCClient(Protocol):
    def sites(self) -> list[dict]: ...
    def query(self, site_url: str, day: str, dataset: str, search_type: str, start_row: int, row_limit: int) -> dict: ...


def normalize_error(error) -> GSCError:
    if isinstance(error, HttpError):
        status = int(error.resp.status)
        try:
            reason = json.loads(error.content).get("error", {}).get("errors", [{}])[0].get("reason", "")
        except (ValueError, IndexError, TypeError):
            reason = ""
        retry_after = error.resp.get("retry-after")
        try:
            delay = float(retry_after) if retry_after else None
        except ValueError:
            try:
                delay = max(0, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                delay = None
        if status == 401:
            return GSCError("reauthorization_required", "Google yêu cầu xác thực lại. Hãy kết nối lại trong Cài đặt.", 401)
        if status == 429 or reason in ("rateLimitExceeded", "userRateLimitExceeded", "quotaExceeded", "dailyLimitExceeded"):
            return GSCError("quota_exceeded", "Google đang giới hạn quota. Chờ rồi thử đồng bộ lại; dữ liệu cũ được giữ nguyên.", 429, True, delay)
        if status == 403:
            return GSCError("permission_denied", "Không đủ quyền property hoặc Search Console API chưa được bật. Kiểm tra Google Cloud và quyền GSC.", 403)
        if status == 404:
            return GSCError("property_unavailable", "Google không tìm thấy property đã chọn.", 404)
        return GSCError("google_server_error" if status >= 500 else "google_request_error", "Google chưa xử lý được yêu cầu. Kiểm tra cấu hình hoặc thử lại sau.", 502, status >= 500, delay)
    if isinstance(error, RefreshError):
        return GSCError("reauthorization_required", "Refresh token đã hết hạn hoặc bị thu hồi. Hãy kết nối lại Google.", 401)
    return GSCError("network_error", "Không thể kết nối Google. Kiểm tra Internet; dữ liệu SQLite đã lưu không bị ảnh hưởng.", 503, True)


class GoogleGSCClient:
    def __init__(self, oauth, connection_id: str, on_retry=None, sleep=time.sleep):
        self.oauth, self.connection_id = oauth, connection_id
        self.on_retry, self.sleep = on_retry, sleep

    def _call(self, operation):
        for attempt in range(4):
            try:
                credentials = self.oauth.credentials(self.connection_id)
                http = google_auth_httplib2.AuthorizedHttp(credentials, http=httplib2.Http(timeout=30))
                service = build("searchconsole", "v1", http=http, cache_discovery=False)
                result = operation(service).execute(num_retries=0)
                self.oauth.save_credentials(self.connection_id, credentials)
                return result
            except GSCError as error:
                failure = error
            except (HttpError, RefreshError, TransportError, httplib2.HttpLib2Error, OSError, TimeoutError) as error:
                failure = normalize_error(error)
            if failure.code == "reauthorization_required":
                self.oauth.mark_reauthorization(self.connection_id)
            if not failure.retryable or attempt == 3 or (failure.retry_after or 0) > 60:
                raise failure
            if self.on_retry:
                self.on_retry()
            self.sleep(max(failure.retry_after or 0, 2 ** attempt + random.uniform(0, 0.5)))

    def sites(self) -> list[dict]:
        return self._call(lambda service: service.sites().list()).get("siteEntry", [])

    def query(self, site_url: str, day: str, dataset: str, search_type: str, start_row: int, row_limit: int) -> dict:
        body = {"startDate": day, "endDate": day, "dimensions": DIMENSIONS[dataset], "type": search_type,
                "aggregationType": "byPage" if dataset == "page" else "byProperty", "dataState": "final",
                "rowLimit": row_limit, "startRow": start_row}
        return self._call(lambda service: service.searchanalytics().query(siteUrl=site_url, body=body))


class FixtureGSCClient:
    """Explicit SQLite test source, never presented as an authorized Google account.

    Site totals intentionally exceed detailed rows, demonstrating privacy/API gaps.
    """
    def sites(self):
        return [{"siteUrl": "sc-domain:fixture.example", "permissionLevel": "siteOwner"},
                {"siteUrl": "https://fixture.example/", "permissionLevel": "siteFullUser"}]

    def query(self, site_url, day, dataset, search_type, start_row, row_limit):
        ordinal = date.fromisoformat(day).toordinal()
        factor = {"web": 1, "image": .22, "video": .12, "news": .07}[search_type]
        base = round((110 + ordinal % 21) * factor)
        keys = {"site": [""], "page": [f"https://fixture.example/trang-{i}" for i in range(1, 13)],
                "query": [f"túi xách thử nghiệm {i}" for i in range(1, 17)],
                "country": ["vnm", "usa", "sgp", "tha", "mys"], "device": ["MOBILE", "DESKTOP", "TABLET"]}[dataset]
        rows = []
        for i, key in enumerate(keys):
            fraction = {"page": .25 / (i + 1), "query": .2 / (i + 1),
                        "country": (.74, .1, .07, .04, .03)[i] if dataset == "country" else 0,
                        "device": (.64, .28, .06)[i] if dataset == "device" else 0}.get(dataset, 1)
            clicks = base if dataset == "site" else max(0, round(base * fraction))
            impressions = clicks * (15 + i) + ordinal % 7
            rows.append({"keys": [] if dataset == "site" else [key], "clicks": clicks, "impressions": impressions,
                         "ctr": clicks / impressions if impressions else 0, "position": 4.5 + i * .3 + ordinal % 9 * .1})
        return {"rows": rows[start_row:start_row + row_limit], "responseAggregationType": "byPage" if dataset == "page" else "byProperty"}
