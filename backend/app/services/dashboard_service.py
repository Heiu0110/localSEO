from collections import defaultdict
from datetime import timedelta
from functools import lru_cache
from typing import Iterable

from app.models import (Change, Changes, CountryReport, CountryRow, DimensionReport,
                        DimensionRow, Metrics, Overview, PageDetail, Performance,
                        PerformancePoint, Period)
from app.providers.base import DataProvider, Observation
from app.providers.mock_provider import MockProvider
from app.services.errors import ResourceNotFoundError


def aggregate(rows: Iterable[Observation]) -> Metrics:
    clicks, impressions, weighted = 0, 0, 0.0
    for row in rows:
        clicks += row.clicks
        impressions += row.impressions
        weighted += row.impressions * row.position
    return Metrics(clicks=clicks, impressions=impressions,
                   ctr=clicks / impressions * 100 if impressions else 0,
                   position=weighted / impressions if impressions else 0)


def change(current: float, previous: float) -> Change:
    return Change(delta=current - previous,
                  percent=(current - previous) / previous * 100 if previous else None)


class DashboardService:
    def __init__(self, provider: DataProvider) -> None:
        self.provider = provider

    def validate_site(self, site_id: str) -> None:
        if site_id not in {site.id for site in self.provider.sites}:
            raise ResourceNotFoundError("Site not found")

    def period(self, days: int, previous: bool = False) -> Period:
        end = self.provider.end_date - timedelta(days=days if previous else 0)
        return Period(start=end - timedelta(days=days - 1), end=end, days=days)

    def rows(self, site_id: str, days: int, previous: bool = False, page_id: str | None = None) -> list[Observation]:
        self.validate_site(site_id)
        period = self.period(days, previous)
        return [r for r in self.provider.observations(site_id)
                if period.start <= r.day <= period.end and (page_id is None or r.page_id == page_id)]

    def overview(self, site_id: str, days: int) -> Overview:
        current = aggregate(self.rows(site_id, days))
        previous = aggregate(self.rows(site_id, days, True))
        changes = Changes(**{key: change(getattr(current, key), getattr(previous, key))
                             for key in Metrics.model_fields})
        return Overview(site_id=site_id, period=self.period(days), previous_period=self.period(days, True),
                        current=current, previous=previous, changes=changes,
                        last_updated=self.provider.last_updated, dataset_start=self.provider.start_date,
                        dataset_end=self.provider.end_date)

    def performance(self, site_id: str, days: int, page_id: str | None = None) -> Performance:
        current: dict = defaultdict(list)
        previous: dict = defaultdict(list)
        for row in self.rows(site_id, days, page_id=page_id):
            current[row.day].append(row)
        for row in self.rows(site_id, days, True, page_id):
            previous[row.day].append(row)
        points = []
        for i in range(days):
            day = self.period(days).start + timedelta(days=i)
            previous_day = day - timedelta(days=days)
            points.append(PerformancePoint(date=day, metrics=aggregate(current[day]),
                                          previous_date=previous_day, previous_metrics=aggregate(previous[previous_day])))
        return Performance(site_id=site_id, period=self.period(days), points=points)

    def dimensions(self, site_id: str, days: int, dimension: str, page_id: str | None = None) -> DimensionReport:
        self.validate_site(site_id)
        labels = self.provider.pages(site_id) if dimension == "page_id" else self.provider.queries(site_id)
        current: dict = defaultdict(list)
        previous: dict = defaultdict(list)
        for row in self.rows(site_id, days, page_id=page_id):
            current[getattr(row, dimension)].append(row)
        for row in self.rows(site_id, days, True, page_id):
            previous[getattr(row, dimension)].append(row)
        result = []
        for key in current.keys() | previous.keys():
            now, before = aggregate(current[key]), aggregate(previous[key])
            result.append(DimensionRow(id=key, label=labels[key], metrics=now, previous=before,
                                       click_change_pct=change(now.clicks, before.clicks).percent))
        result.sort(key=lambda r: (-r.metrics.clicks, r.id))
        return DimensionReport(site_id=site_id, period=self.period(days), rows=result)

    def countries(self, site_id: str, days: int) -> CountryReport:
        groups: dict = defaultdict(list)
        rows = self.rows(site_id, days)
        total = aggregate(rows).clicks
        for row in rows:
            groups[row.country].append(row)
        result = []
        for code, group in groups.items():
            metrics = aggregate(group)
            result.append(CountryRow(code=code, name=self.provider.countries[code], metrics=metrics,
                                     share=metrics.clicks / total * 100 if total else 0))
        return CountryReport(site_id=site_id, period=self.period(days), rows=sorted(result, key=lambda r: -r.metrics.clicks))

    def page_detail(self, site_id: str, days: int, page_id: str) -> PageDetail:
        self.validate_site(site_id)
        if page_id not in self.provider.pages(site_id):
            raise ResourceNotFoundError("Page not found")
        return PageDetail(id=page_id, url=self.provider.pages(site_id)[page_id], period=self.period(days),
                          current=aggregate(self.rows(site_id, days, page_id=page_id)),
                          previous=aggregate(self.rows(site_id, days, True, page_id)),
                          performance=self.performance(site_id, days, page_id).points,
                          queries=self.dimensions(site_id, days, "query_id", page_id).rows)


@lru_cache
def get_service() -> DashboardService:
    return DashboardService(MockProvider())
