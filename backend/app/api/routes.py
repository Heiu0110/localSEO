from enum import IntEnum
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models import (CountryReport, DataSource, DimensionReport, Health,
                        Overview, PageDetail, Performance, Site)
from app.services.dashboard_service import DashboardService, get_service
from app.gsc.runtime import get_runtime
from app.gsc.schemas import SearchType
from app.gsc.errors import GSCError
from app.gsc.repository import properties_view
from app.providers.sqlite_provider import SQLiteAnalyticsProvider

router = APIRouter(prefix="/api")
Service = Annotated[DashboardService, Depends(get_service)]


class DateRange(IntEnum):
    week = 7
    month = 28
    quarter = 90


Days = Annotated[DateRange, Query(description="Inclusive days, ending at mock dataset end")]
SiteId = Annotated[str, Query(min_length=1, max_length=100)]


def resolve_report(site_id: SiteId, search_type: SearchType = "web", end_date: date | None = None):
    mock = get_service()
    if site_id in {site.id for site in mock.provider.sites}:
        if search_type != "web":
            raise GSCError("unsupported_demo_type", "Demo chỉ mô phỏng Web Search.", 422)
        return mock
    from app.db.models import Property
    from app.services.errors import ResourceNotFoundError
    with get_runtime().db.session() as session:
        prop = session.get(Property, site_id)
        if not prop or not prop.is_active:
            raise ResourceNotFoundError("Site not found")
    return SQLiteAnalyticsProvider(get_runtime().db, search_type, end=end_date)


Report = Annotated[object, Depends(resolve_report)]


@router.get("/health", response_model=Health)
def health():
    return Health()


@router.get("/sites", response_model=list[Site])
def sites(service: Service):
    return list(service.provider.sites) + [Site(id=p.id, domain=p.site_url, source_type=p.source_type)
        for p in properties_view(get_runtime().db) if p.is_active]


@router.get("/dashboard/overview", response_model=Overview)
def overview(service: Report, site_id: SiteId, days: Days = DateRange.month):
    return service.overview(site_id, days)


@router.get("/dashboard/performance", response_model=Performance)
def performance(service: Report, site_id: SiteId, days: Days = DateRange.month):
    return service.performance(site_id, days)


@router.get("/dashboard/pages", response_model=DimensionReport)
def pages(service: Report, site_id: SiteId, days: Days = DateRange.month):
    return service.dimensions(site_id, days, "page_id")


@router.get("/dashboard/queries", response_model=DimensionReport)
def queries(service: Report, site_id: SiteId, days: Days = DateRange.month):
    return service.dimensions(site_id, days, "query_id")


@router.get("/dashboard/countries", response_model=CountryReport)
def countries(service: Report, site_id: SiteId, days: Days = DateRange.month):
    return service.countries(site_id, days)


@router.get("/dashboard/pages/{page_id}", response_model=PageDetail)
def page_detail(page_id: str, service: Report, site_id: SiteId, days: Days = DateRange.month):
    return service.page_detail(site_id, days, page_id)


@router.get("/dashboard/sources", response_model=list[DataSource])
def sources(site_id: str | None = None):
    result = [
        DataSource(id="gsc", name="Google Search Console", status="Mock Mode", detail="Deterministic demo data · no Google connection"),
        DataSource(id="ga4", name="Google Analytics 4", status="Not Connected", detail="Sessions and engagement · future integration"),
        DataSource(id="technical", name="Technical SEO", status="Planned", detail="Crawl and indexability · future release"),
        DataSource(id="backlinks", name="Backlink Provider", status="Not Configured", detail="External provider · future integration"),
        DataSource(id="ai", name="AI SEO Analyst", status="Planned", detail="Evidence-based insights · future release"),
    ]
    if site_id and site_id not in {s.id for s in get_service().provider.sites}:
        from app.db.models import Connection
        from app.gsc.dates import bounds
        from datetime import date, timedelta
        runtime = get_runtime()
        provider = SQLiteAnalyticsProvider(runtime.db)
        prop = provider.prop(site_id)
        jobs = runtime.sync.jobs(site_id)
        with runtime.db.session() as session:
            connection = session.get(Connection, prop.connection_id)
        if prop.source_type == "fixture":
            state = "Fixture"
        elif connection.status == "disconnected":
            state = "Not Connected"
        elif connection.status == "reauthorization_required":
            state = "Reauthorization Required"
        elif jobs and jobs[0].status in ("queued", "running"):
            state = "Syncing"
        elif jobs and jobs[0].status in ("failed", "partial"):
            state = "Error"
        elif not prop.last_synced_at:
            state = "Connected" if connection.status == "connected" else "Not Connected"
        else:
            latest = provider.period(site_id, 7).end
            state = "Stale" if latest < bounds()[1] - timedelta(days=7) else "Up to Date"
        result[0] = DataSource(id="gsc", name="Google Search Console", status=state, detail="SQLite cục bộ · " + prop.site_url)
    return result
