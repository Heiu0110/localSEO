from enum import IntEnum
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models import (CountryReport, DataSource, DimensionReport, Health,
                        Overview, PageDetail, Performance, Site)
from app.services.dashboard_service import DashboardService, get_service

router = APIRouter(prefix="/api")
Service = Annotated[DashboardService, Depends(get_service)]


class DateRange(IntEnum):
    week = 7
    month = 28
    quarter = 90


Days = Annotated[DateRange, Query(description="Inclusive days, ending at mock dataset end")]
SiteId = Annotated[str, Query(min_length=1, max_length=100)]


@router.get("/health", response_model=Health)
def health():
    return Health()


@router.get("/sites", response_model=list[Site])
def sites(service: Service):
    return service.provider.sites


@router.get("/dashboard/overview", response_model=Overview)
def overview(service: Service, site_id: SiteId, days: Days = DateRange.month):
    return service.overview(site_id, days)


@router.get("/dashboard/performance", response_model=Performance)
def performance(service: Service, site_id: SiteId, days: Days = DateRange.month):
    return service.performance(site_id, days)


@router.get("/dashboard/pages", response_model=DimensionReport)
def pages(service: Service, site_id: SiteId, days: Days = DateRange.month):
    return service.dimensions(site_id, days, "page_id")


@router.get("/dashboard/queries", response_model=DimensionReport)
def queries(service: Service, site_id: SiteId, days: Days = DateRange.month):
    return service.dimensions(site_id, days, "query_id")


@router.get("/dashboard/countries", response_model=CountryReport)
def countries(service: Service, site_id: SiteId, days: Days = DateRange.month):
    return service.countries(site_id, days)


@router.get("/dashboard/pages/{page_id}", response_model=PageDetail)
def page_detail(page_id: str, service: Service, site_id: SiteId, days: Days = DateRange.month):
    return service.page_detail(site_id, days, page_id)


@router.get("/dashboard/sources", response_model=list[DataSource])
def sources():
    return [
        DataSource(id="gsc", name="Google Search Console", status="Mock Mode", detail="Deterministic demo data · no Google connection"),
        DataSource(id="ga4", name="Google Analytics 4", status="Not Connected", detail="Sessions and engagement · future integration"),
        DataSource(id="technical", name="Technical SEO", status="Planned", detail="Crawl and indexability · future release"),
        DataSource(id="backlinks", name="Backlink Provider", status="Not Configured", detail="External provider · future integration"),
        DataSource(id="ai", name="AI SEO Analyst", status="Planned", detail="Evidence-based insights · future release"),
    ]
