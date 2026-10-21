import csv
import io
import secrets
import tempfile
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from app.db.models import Property, SyncJob
from app.gsc.client import FixtureGSCClient, GoogleGSCClient
from app.gsc.errors import GSCError
from app.gsc.repository import create_fixture_properties, properties_view, register_properties, require_property
from app.gsc.runtime import Runtime, get_runtime
from app.gsc.schemas import (DisconnectRequest, DisconnectResult, IntegrationStatus, JobView,
                            PropertySelection, PropertyView, SearchType, SyncRequest)
from app.models import DimensionReport, Overview, PageDetail, Performance
from app.providers.sqlite_provider import SQLiteAnalyticsProvider

router = APIRouter(prefix="/api")
RuntimeDep = Annotated[Runtime, Depends(get_runtime)]
CSRF_TOKEN = secrets.token_urlsafe(32)


@router.get("/session")
def session_token():
    return Response(content='{"csrf_token":"' + CSRF_TOKEN + '"}', media_type="application/json", headers={"Cache-Control": "no-store"})


@router.get("/integrations/gsc/status", response_model=IntegrationStatus)
def status(runtime: RuntimeDep):
    return runtime.oauth.status()


@router.post("/integrations/gsc/configure", response_model=IntegrationStatus)
async def configure(runtime: RuntimeDep, file: Annotated[UploadFile, File()]):
    try:
        content = await file.read(64 * 1024 + 1)
        runtime.oauth.configure(content)
    finally:
        await file.close()
    return runtime.oauth.status()


@router.post("/integrations/gsc/oauth/start")
def oauth_start(runtime: RuntimeDep):
    return runtime.oauth.start()


@router.get("/integrations/gsc/oauth/callback", response_class=HTMLResponse, include_in_schema=False)
def oauth_callback(runtime: RuntimeDep, state: str = "", code: str | None = None, error: str | None = None):
    runtime.oauth.callback(state, code, error)
    return HTMLResponse('<!doctype html><html lang="vi"><meta charset="utf-8"><title>Đã kết nối Google</title>'
                        '<h1>Đã kết nối Google Search Console</h1><p>Bạn có thể đóng cửa sổ này và quay lại ứng dụng.</p>'
                        '<a href="http://127.0.0.1:5173/settings">Về Cài đặt</a></html>',
                        headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer", "Content-Security-Policy": "default-src 'none'; base-uri 'none'; frame-ancestors 'none'"})


@router.post("/integrations/gsc/disconnect", response_model=DisconnectResult)
def disconnect(body: DisconnectRequest, runtime: RuntimeDep):
    if any(job.status in ("queued", "running") for job in runtime.sync.jobs()):
        raise GSCError("sync_active", "Hãy hủy hoặc chờ đồng bộ hoàn tất trước khi ngắt kết nối.", 409)
    return runtime.oauth.disconnect(body.revoke)


@router.get("/integrations/gsc/properties", response_model=list[PropertyView])
def properties(runtime: RuntimeDep):
    return properties_view(runtime.db)


@router.post("/integrations/gsc/properties/refresh", response_model=list[PropertyView])
def refresh_properties(runtime: RuntimeDep):
    connection_id = runtime.oauth.connection_id()
    if not connection_id:
        raise GSCError("not_connected", "Hãy kết nối Google trước.", 409)
    entries = GoogleGSCClient(runtime.oauth, connection_id).sites()
    register_properties(runtime.db, connection_id, entries, "gsc")
    return properties_view(runtime.db)


@router.post("/integrations/gsc/properties", response_model=list[PropertyView])
def select_property(body: PropertySelection, runtime: RuntimeDep):
    with runtime.db.session.begin() as session:
        prop = require_property(session, body.property_id)
        if session.scalar(select(SyncJob).where(SyncJob.property_id == prop.id, SyncJob.status.in_(("queued", "running")))):
            raise GSCError("sync_active", "Chờ hoặc hủy đồng bộ trước khi thay đổi property.", 409)
        prop.is_active = body.is_active
    return properties_view(runtime.db)


@router.post("/integrations/gsc/fixtures", response_model=list[PropertyView])
def fixtures(runtime: RuntimeDep):
    create_fixture_properties(runtime.db, FixtureGSCClient())
    return properties_view(runtime.db)


@router.post("/gsc/sync/start", response_model=JobView, status_code=202)
def sync_start(body: SyncRequest, runtime: RuntimeDep):
    return runtime.sync.start(body)


@router.get("/gsc/sync/jobs", response_model=list[JobView])
def sync_jobs(runtime: RuntimeDep, property_id: str | None = None):
    return runtime.sync.jobs(property_id)


@router.get("/gsc/sync/jobs/{job_id}", response_model=JobView)
def sync_job(job_id: str, runtime: RuntimeDep):
    return runtime.sync.job(job_id)


@router.post("/gsc/sync/jobs/{job_id}/cancel", response_model=JobView)
def cancel_job(job_id: str, runtime: RuntimeDep):
    return runtime.sync.cancel(job_id)


@router.post("/gsc/sync/jobs/{job_id}/retry", response_model=JobView, status_code=202)
def retry_job(job_id: str, runtime: RuntimeDep):
    return runtime.sync.retry(job_id)


def analytics_provider(runtime: RuntimeDep, start_date: date, end_date: date, search_type: SearchType = "web"):
    if start_date > end_date or (end_date - start_date).days > 500:
        raise GSCError("invalid_report_range", "Chọn khoảng ngày hợp lệ, tối đa 501 ngày.", 422)
    return SQLiteAnalyticsProvider(runtime.db, search_type, start_date, end_date)


Analytics = Annotated[SQLiteAnalyticsProvider, Depends(analytics_provider)]


@router.get("/gsc/analytics/overview", response_model=Overview)
def analytics_overview(provider: Analytics, property_id: str):
    return provider.overview(property_id, 28)


@router.get("/gsc/analytics/performance", response_model=Performance)
def analytics_performance(provider: Analytics, property_id: str):
    return provider.performance(property_id, 28)


@router.get("/gsc/analytics/pages/detail", response_model=PageDetail)
def analytics_page(provider: Analytics, property_id: str, page_id: str):
    return provider.page_detail(property_id, 28, page_id)


@router.get("/gsc/analytics/{dataset}", response_model=DimensionReport)
def analytics_rows(provider: Analytics, property_id: str, dataset: Literal["pages", "queries", "countries", "devices"],
                   page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100), search: str = Query("", max_length=500),
                   sort: Literal["label", "clicks", "impressions", "ctr", "position", "click_change_pct", "impression_change_pct"] = "clicks",
                   direction: Literal["asc", "desc"] = "desc"):
    dimension = {"pages": "page", "queries": "query", "countries": "country", "devices": "device"}[dataset]
    return provider.dimensions(property_id, 28, dimension, page=page, page_size=page_size, search=search, sort=sort, direction=direction)


@router.get("/gsc/export/{dataset}")
def export(provider: Analytics, property_id: str, dataset: Literal["pages", "queries", "countries", "devices"],
           search: str = Query("", max_length=500), sort: Literal["label", "clicks", "impressions", "ctr", "position", "click_change_pct", "impression_change_pct"] = "clicks",
           direction: Literal["asc", "desc"] = "desc"):
    dimension = {"pages": "page", "queries": "query", "countries": "country", "devices": "device"}[dataset]
    # A bounded streamed export avoids loading a full multi-month dataset into the browser.
    from fastapi.responses import StreamingResponse

    def generate_unlocked():
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["Nguồn", "Property", "Từ ngày", "Đến ngày", "Search type", "Phạm vi", "Giá trị", "Lượt nhấp", "Lượt hiển thị", "CTR (%)", "Vị trí TB", "Thay đổi nhấp (%)", "Thay đổi hiển thị (%)"])
        yield "\ufeff" + buffer.getvalue()
        page = 1
        while True:
            report = provider.dimensions(property_id, 28, dimension, page=page, page_size=1000, search=search, sort=sort, direction=direction)
            if not report.rows:
                break
            prop = provider.prop(property_id)
            buffer.seek(0)
            buffer.truncate(0)
            for row in report.rows:
                safe = lambda text: "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text
                writer.writerow([prop.source_type, safe(prop.site_url), report.period.start, report.period.end, provider.search_type,
                    "Dữ liệu đã lưu; API có thể giới hạn", safe(row.label), row.metrics.clicks if row.current_available else "", row.metrics.impressions if row.current_available else "",
                    row.metrics.ctr if row.current_available else "", row.metrics.position if row.current_available else "", row.click_change_pct, row.impression_change_pct])
            yield buffer.getvalue()
            if page * 1000 >= report.total_rows:
                break
            page += 1

    def generate():
        # Finish a stable export under the writer lock, then stream without holding
        # a thread-owned lock across ASGI threadpool yields. Large exports spill to disk.
        with tempfile.SpooledTemporaryFile(max_size=1024 * 1024, mode="w+t", encoding="utf-8", newline="") as spool:
            with provider.db.metrics_lock:
                for chunk in generate_unlocked():
                    spool.write(chunk)
            spool.seek(0)
            while chunk := spool.read(64 * 1024):
                yield chunk

    # Validate the selection before HTTP headers are committed by StreamingResponse.
    provider.prop(property_id)
    filename = f"stored-{dataset}-{property_id}-{provider.start}-{provider.end}-{provider.search_type}.csv"
    return StreamingResponse(generate(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})
