"""Report-level adapter. Independent GSC datasets never become a synthetic fact cube."""
import base64
from functools import wraps
from datetime import date, datetime, timedelta, timezone

import pycountry
from sqlalchemy import Float, case, cast, func, literal, select, union

from app.db.models import Checkpoint, MetricFact, Property
from app.gsc.dates import bounds
from app.gsc.errors import GSCError
from app.gsc.repository import require_property
from app.gsc.schemas import Coverage, CoverageReport
from app.models import (Change, Changes, CountryReport, CountryRow, DimensionReport, DimensionRow, Metrics,
                        Overview, PageDetail, Performance, PerformancePoint, Period)
from app.services.dashboard_service import change

DETAIL_WARNING = "Các dòng đã lưu có thể thiếu truy vấn ẩn danh hoặc bị giới hạn API. Không dùng tổng bảng chi tiết thay KPI cấp property."


def consistent_report(method):
    @wraps(method)
    def report(self, *args, **kwargs):
        with self.db.metrics_lock:
            return method(self, *args, **kwargs)
    return report


def dimension_id(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def decode_id(value: str) -> str:
    try:
        return base64.b64decode(value + "=" * (-len(value) % 4), altchars=b"-_", validate=True).decode()
    except (ValueError, UnicodeError):
        raise GSCError("page_not_found", "Không tìm thấy URL đã lưu.", 404) from None


def country_info(code: str):
    country = pycountry.countries.get(alpha_3=code.upper()) or pycountry.countries.get(alpha_2=code.upper())
    return (country.alpha_2, country.name) if country else (code.upper(), f"Không xác định ({code.upper()})")


def metrics(clicks=0, impressions=0, weighted=0) -> Metrics:
    return Metrics(clicks=int(clicks or 0), impressions=int(impressions or 0),
                   ctr=clicks / impressions * 100 if impressions else 0,
                   position=weighted / impressions if impressions else 0)


class SQLiteAnalyticsProvider:
    def __init__(self, db, search_type="web", start: date | None = None, end: date | None = None):
        self.db, self.search_type, self.start, self.end = db, search_type, start, end

    def prop(self, site_id):
        with self.db.session() as session:
            return require_property(session, site_id, active=True)

    def period(self, site_id, days, previous=False):
        with self.db.session() as session:
            latest = session.scalar(select(func.max(MetricFact.date)).where(MetricFact.property_id == site_id,
                MetricFact.search_type == self.search_type, MetricFact.dataset_type == "site", MetricFact.data_state == "final"))
        end = self.end or (date.fromisoformat(latest) if latest else bounds()[1])
        start = self.start or end - timedelta(days=int(days) - 1)
        length = (end - start).days + 1
        if previous:
            start, end = start - timedelta(days=length), start - timedelta(days=1)
        return Period(start=start, end=end, days=length)

    def where(self, site_id, period, dataset, value=None):
        conditions = [MetricFact.property_id == site_id, MetricFact.search_type == self.search_type,
                      MetricFact.dataset_type == dataset, MetricFact.date >= period.start.isoformat(),
                      MetricFact.date <= period.end.isoformat(), MetricFact.data_state == "final",
                      MetricFact.aggregation_type == ("byPage" if dataset == "page" else "byProperty")]
        if value is not None:
            conditions.append(MetricFact.dimension_value == value)
        return conditions

    def total(self, site_id, period, dataset="site", value=None):
        with self.db.session() as session:
            row = session.execute(select(func.sum(MetricFact.clicks), func.sum(MetricFact.impressions),
                func.sum(MetricFact.position * MetricFact.impressions)).where(*self.where(site_id, period, dataset, value))).one()
            return metrics(*row)

    def coverage(self, site_id, period, dataset="site") -> Coverage:
        with self.db.session() as session:
            rows = list(session.scalars(select(Checkpoint).where(Checkpoint.property_id == site_id, Checkpoint.search_type == self.search_type,
                Checkpoint.dataset_type == dataset, Checkpoint.date >= period.start.isoformat(), Checkpoint.date <= period.end.isoformat())))
        available = sum(r.status == "complete" for r in rows)
        completeness = "api_limited" if any(r.completeness == "api_limited" for r in rows) else "api_response" if len(rows) == period.days else "unknown"
        return Coverage(expected_days=period.days, synchronized_days=len(rows), available_days=available,
                        empty_days=sum(r.status == "empty" for r in rows), completeness=completeness,
                        aggregation_type="byPage" if dataset == "page" else "byProperty")

    @consistent_report
    def overview(self, site_id, days):
        prop = self.prop(site_id)
        period, previous_period = self.period(site_id, days), self.period(site_id, days, True)
        current, previous = self.total(site_id, period), self.total(site_id, previous_period)
        coverage, before = self.coverage(site_id, period), self.coverage(site_id, previous_period)
        comparable = coverage.available_days == period.days and before.available_days == period.days
        warnings = []
        if coverage.available_days < period.days:
            warnings.append(f"Có số liệu cấp property cho {coverage.available_days}/{period.days} ngày; {coverage.empty_days} ngày API trả rỗng. KPI chỉ tổng hợp ngày có bản ghi, không suy diễn ngày thiếu thành 0.")
        if not comparable:
            warnings.append("Chưa đủ dữ liệu lịch sử để so sánh hai kỳ đầy đủ.")
        with self.db.session() as session:
            first, last = session.execute(select(func.min(MetricFact.date), func.max(MetricFact.date)).where(
                MetricFact.property_id == site_id, MetricFact.search_type == self.search_type, MetricFact.dataset_type == "site")).one()
        report_coverage = CoverageReport(current=coverage, previous=before, comparison_available=comparable, warnings=warnings)
        return Overview(site_id=site_id, period=period, previous_period=previous_period, current=current, previous=previous,
            changes=Changes(**{key: change(getattr(current, key), getattr(previous, key)) if comparable else Change(delta=None, percent=None) for key in Metrics.model_fields}),
            source=prop.source_type, last_updated=prop.last_synced_at or datetime(1970, 1, 1, tzinfo=timezone.utc),
            dataset_start=first or period.start, dataset_end=last or period.end, has_data=coverage.available_days > 0,
            comparison_available=comparable, coverage=report_coverage.model_dump(), warnings=warnings, last_synced_at=prop.last_synced_at)

    @consistent_report
    def performance(self, site_id, days, page_id=None):
        self.prop(site_id)
        period, before = self.period(site_id, days), self.period(site_id, days, True)
        dataset, value = ("page", decode_id(page_id)) if page_id else ("site", None)
        by_day = []
        for window in (period, before):
            with self.db.session() as session:
                rows = session.execute(select(MetricFact.date, func.sum(MetricFact.clicks), func.sum(MetricFact.impressions),
                    func.sum(MetricFact.position * MetricFact.impressions)).where(*self.where(site_id, window, dataset, value)).group_by(MetricFact.date)).all()
                by_day.append({r[0]: metrics(*r[1:]) for r in rows})
        points = []
        for i in range(period.days):
            current_day, previous_day = period.start + timedelta(days=i), before.start + timedelta(days=i)
            points.append(PerformancePoint(date=current_day, previous_date=previous_day,
                metrics=by_day[0].get(current_day.isoformat()), previous_metrics=by_day[1].get(previous_day.isoformat())))
        return Performance(site_id=site_id, period=period, points=points)

    def _group(self, site_id, period, dataset):
        return select(MetricFact.dimension_value.label("value"), func.sum(MetricFact.clicks).label("clicks"),
                      func.sum(MetricFact.impressions).label("impressions"),
                      func.sum(MetricFact.position * MetricFact.impressions).label("weighted")).where(
                          *self.where(site_id, period, dataset)).group_by(MetricFact.dimension_value).subquery()

    @consistent_report
    def dimensions(self, site_id, days, dimension, page_id=None, page=1, page_size=100, search="", sort="clicks", direction="desc"):
        self.prop(site_id)
        dataset = {"page_id": "page", "query_id": "query"}.get(dimension, dimension)
        if dataset not in ("page", "query", "country", "device"):
            raise GSCError("invalid_dimension", "Dimension không được hỗ trợ.", 422)
        period, before = self.period(site_id, days), self.period(site_id, days, True)
        current, previous = self._group(site_id, period, dataset), self._group(site_id, before, dataset)
        keys = union(select(current.c.value), select(previous.c.value)).subquery()
        joined = keys.outerjoin(current, keys.c.value == current.c.value).outerjoin(previous, keys.c.value == previous.c.value)
        clicks, impressions = func.coalesce(current.c.clicks, 0), func.coalesce(current.c.impressions, 0)
        allowed = {"label": keys.c.value, "clicks": current.c.clicks, "impressions": current.c.impressions,
                   "ctr": cast(current.c.clicks, Float) / func.nullif(current.c.impressions, 0), "position": current.c.weighted / func.nullif(impressions, 0),
                   "click_change_pct": cast(current.c.clicks - previous.c.clicks, Float) / func.nullif(previous.c.clicks, 0),
                   "impression_change_pct": cast(current.c.impressions - previous.c.impressions, Float) / func.nullif(previous.c.impressions, 0)}
        if sort not in allowed or direction not in ("asc", "desc"):
            raise GSCError("invalid_sort", "Khóa sắp xếp không hợp lệ.", 422)
        query = select(keys.c.value, current.c.clicks, current.c.impressions, current.c.weighted,
                       previous.c.clicks.label("prior_clicks"), previous.c.impressions.label("prior_impressions"), previous.c.weighted.label("prior_weighted")).select_from(joined)
        if search:
            query = query.where(keys.c.value.icontains(search, autoescape=True))
        with self.db.session() as session:
            count = session.scalar(select(func.count()).select_from(query.subquery()))
            order = allowed[sort].asc().nulls_last() if direction == "asc" else allowed[sort].desc().nulls_last()
            result = session.execute(query.order_by(order, keys.c.value).offset((page - 1) * page_size).limit(page_size)).all()
        comparable = self.coverage(site_id, period, dataset).synchronized_days == period.days and self.coverage(site_id, before, dataset).synchronized_days == before.days
        rows = []
        for row in result:
            current_metrics, previous_metrics = metrics(*row[1:4]), metrics(*row[4:7])
            both = comparable and row[1] is not None and row[4] is not None
            label = country_info(row[0])[1] if dataset == "country" else row[0]
            rows.append(DimensionRow(id=dimension_id(row[0]), label=label, metrics=current_metrics, previous=previous_metrics,
                click_change_pct=change(current_metrics.clicks, previous_metrics.clicks).percent if both else None,
                impression_change_pct=change(current_metrics.impressions, previous_metrics.impressions).percent if both else None,
                current_available=row[1] is not None, previous_available=row[4] is not None,
                code=country_info(row[0])[0] if dataset == "country" else row[0] if dataset == "device" else None))
        if dataset in ("country", "device"):
            total = self.total(site_id, period, dataset).clicks
            for row in rows:
                row.share = row.metrics.clicks / total * 100 if total else 0
        return DimensionReport(site_id=site_id, period=period, rows=rows, coverage="partial", total_rows=count,
                               warning=DETAIL_WARNING, page=page, page_size=page_size, completeness=self.coverage(site_id, period, dataset).completeness)

    @consistent_report
    def countries(self, site_id, days):
        report = self.dimensions(site_id, days, "country", page_size=300)
        result = []
        for row in report.rows:
            code, name = country_info(decode_id(row.id))
            result.append(CountryRow(code=code, name=name, metrics=row.metrics, share=min(100, row.share or 0), current_available=row.current_available))
        return CountryReport(site_id=site_id, period=report.period, rows=result, coverage="partial", share_basis="returned_rows")

    @consistent_report
    def page_detail(self, site_id, days, page_id):
        prop = self.prop(site_id)
        value = decode_id(page_id)
        period, before = self.period(site_id, days), self.period(site_id, days, True)
        performance = self.performance(site_id, days, page_id)
        if not any(p.metrics is not None or p.previous_metrics is not None for p in performance.points):
            raise GSCError("page_not_found", "Chưa có dữ liệu theo ngày cho URL này trong kỳ đã chọn.", 404)
        return PageDetail(id=page_id, url=value, period=period, current=self.total(site_id, period, "page", value),
            previous=self.total(site_id, before, "page", value), performance=performance.points, queries=[], source=prop.source_type,
            query_relationships_available=False, has_data=any(p.metrics is not None for p in performance.points),
            comparison_available=all(point.metrics is not None and point.previous_metrics is not None for point in performance.points))
