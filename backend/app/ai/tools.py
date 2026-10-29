"""Versioned allowlist. Model arguments cannot select a different project."""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import date, datetime, timedelta
from typing import Literal
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo
from pydantic import Field, ValidationError
from sqlalchemy import select, func
from app.gsc.errors import GSCError
from app.providers.sqlite_provider import dimension_id
from app.technical.models import AuditIssue, AuditURL, AuditLink
from app.technical import reports as technical_reports
from app.keywords.models import (
    KeywordSet,
    SearchProfile,
    TrackedKeyword,
    RankObservation,
    TrackingWeek,
    KeywordMetric,
)
from app.keywords import reports as keyword_reports
from .schemas import Input, ToolEnvelope
from .common import uid, now, fail, limited, view
from .context import context, project, analytics, audit_run
from app.research.agent_tools import (
    SPECS as RESEARCH_SPECS,
    execute as research_execute,
)


class Empty(Input):
    pass


class Window(Input):
    days: Literal[7, 28, 90] = 28
    end_date: date | None = None


class Rows(Window):
    limit: int = Field(default=10, ge=1, le=10)
    search: str = Field(default="", max_length=200)
    sort: Literal["clicks", "impressions", "click_change_pct"] = "clicks"


class AuditArgs(Input):
    audit_id: str | None = Field(default=None, max_length=100)


class FindingArgs(AuditArgs):
    severity: Literal["", "critical", "high", "medium", "low", "info"] = ""
    search: str = Field(default="", max_length=200)
    limit: int = Field(default=6, ge=1, le=6)


class URLArgs(AuditArgs):
    url: str = Field(min_length=1, max_length=2048)


class LinkArgs(AuditArgs):
    search: str = Field(default="", max_length=200)


class KeywordArgs(Input):
    set_id: str | None = Field(default=None, max_length=100)
    profile_id: str | None = Field(default=None, max_length=100)
    week: int | None = Field(default=None, ge=1, le=520)


class HistoryArgs(Input):
    keyword_id: str = Field(min_length=1, max_length=100)
    profile_id: str | None = Field(default=None, max_length=100)


class QueryPageArgs(Window):
    keyword_id: str = Field(min_length=1, max_length=100)


TOOL_SPECS = {
    "get_project_context": (Empty, "Website và nguồn dữ liệu có sẵn."),
    "get_data_source_status": (Empty, "Độ phủ, thời gian và nguồn dữ liệu còn thiếu."),
    "get_gsc_overview": (
        Window,
        "KPI GSC site/byProperty; tuyệt đối không cộng Top Queries.",
    ),
    "compare_gsc_periods": (
        Window,
        "So sánh GSC với kỳ liền trước bằng dịch vụ hiện có.",
    ),
    "get_gsc_top_pages": (
        Rows,
        "Top URL có giới hạn, có current_available và comparison coverage.",
    ),
    "get_gsc_top_queries": (
        Rows,
        "Top exact queries đã lưu; thiếu query không có nghĩa bằng 0.",
    ),
    "get_gsc_query_page_data": (
        QueryPageArgs,
        "Cache query × target page đã sync riêng; không gọi Google.",
    ),
    "get_technical_audit_summary": (
        AuditArgs,
        "Snapshot Technical SEO thuộc website này.",
    ),
    "get_technical_findings": (
        FindingArgs,
        "Finding kỹ thuật đã lưu, kèm mức độ và thời gian audit.",
    ),
    "get_url_diagnostics": (
        URLArgs,
        "Điều tra đúng URL trong snapshot hiện có, không crawl mới.",
    ),
    "get_internal_link_summary": (
        LinkArgs,
        "Liên kết HTML do crawler quan sát; không suy ra Topical Map.",
    ),
    "get_keyword_tracking_summary": (
        KeywordArgs,
        "Rank MANUAL theo bộ/profile/tuần và biến động hợp lệ.",
    ),
    "get_keyword_rank_history": (
        HistoryArgs,
        "Đại diện rank của tối đa 35 tuần; giữ snapshot profile/URL.",
    ),
}

TOOL_SPECS.update(RESEARCH_SPECS)


def strict_schema(schema):
    if isinstance(schema, dict):
        schema = {k: strict_schema(v) for k, v in schema.items() if k != "default"}
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            schema["required"] = list(schema.get("properties", {}))
    elif isinstance(schema, list):
        schema = [strict_schema(x) for x in schema]
    return schema


def metadata():
    return [
        {
            "name": name,
            "version": "1.0",
            "description": description,
            "input_schema": model.model_json_schema(),
            "output_schema": ToolEnvelope.model_json_schema(),
            "permission": "read_only",
            "project_scope": "conversation.project_id (server enforced)",
            "timeout_seconds": 5,
            "max_result_bytes": 8000,
        }
        for name, (model, description) in TOOL_SPECS.items()
    ]


class ToolRegistry:
    def __init__(self, db):
        self.db = db
        self.executor = ThreadPoolExecutor(
            max_workers=2, thread_name_prefix="ai-read-tool"
        )
        self.slots = threading.BoundedSemaphore(2)

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)

    def definitions(self):
        return [
            {
                "type": "function",
                "name": name,
                "description": description,
                "parameters": strict_schema(model.model_json_schema()),
                "strict": True,
            }
            for name, (model, description) in TOOL_SPECS.items()
        ]

    def execute(self, name, args, project_id, timeout=5):
        if name not in TOOL_SPECS:
            fail("ai_tool_not_allowed", "Tool không thuộc allowlist chỉ đọc.", 403)
        try:
            args = TOOL_SPECS[name][0].model_validate(args)
        except ValidationError:
            fail(
                "ai_invalid_tool_arguments",
                "Đối số tool không hợp lệ; không hỗ trợ project_id, SQL, shell hoặc đường dẫn file.",
            )
        p = project(self.db, project_id)
        if not self.slots.acquire(blocking=False):
            fail("ai_tools_busy", "Tool đang bận. Thử lại sau.", 409)

        def invoke():
            try:
                return self._execute(name, args, p)
            finally:
                self.slots.release()

        future = self.executor.submit(invoke)
        try:
            return ToolEnvelope.model_validate(
                limited(future.result(timeout=timeout))
            ).model_dump(mode="json")
        except TimeoutError:
            fail(
                "ai_tool_timeout",
                "Tool vượt thời gian xử lý; dữ liệu SEO không bị thay đổi.",
                504,
            )
        except GSCError:
            raise
        except Exception:
            fail(
                "ai_tool_error",
                "Không đọc được nguồn dữ liệu đã chọn. Thử lại hoặc kiểm tra nguồn.",
                503,
            )

    def evidence(
        self,
        p,
        source,
        data,
        record=None,
        scope="project",
        start=None,
        end=None,
        collected=None,
        reference=None,
        completeness="unknown",
        limitations=None,
    ):
        age = None
        try:
            age = (
                max(
                    0,
                    (
                        datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
                        - datetime.fromisoformat(
                            collected.replace("Z", "+00:00")
                        ).date()
                    ).days,
                )
                if collected
                else None
            )
        except (ValueError, TypeError):
            pass
        reporting_lag = (
            max(
                0,
                (
                    datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).date()
                    - date.fromisoformat(str(end))
                ).days,
            )
            if end
            else None
        )
        stale = (age is not None and age > 14) or (
            reporting_lag is not None and reporting_lag > 7
        )
        return {
            "evidence": {
                "evidence_id": uid(),
                "project_id": p["id"],
                "source_type": source,
                "source_name": {
                    "workspace_context": "Ngữ cảnh website",
                    "demo_gsc": "GSC mô phỏng",
                    "fixture_gsc": "GSC thử nghiệm",
                    "GSC": "Google Search Console",
                    "Technical Crawl": "Crawl kỹ thuật",
                    "Keyword Tracking": "Keyword Tracking",
                }.get(source, source),
                "source_record_id": record,
                "metric_scope": scope,
                "date_start": str(start) if start else None,
                "date_end": str(end) if end else None,
                "collected_at": collected,
                "retrieved_at": now(),
                "data_freshness": {
                    "age_days": age,
                    "reporting_lag_days": reporting_lag,
                    "status": (
                        "stale" if stale else "unknown" if age is None else "recent"
                    ),
                },
                "completeness": completeness,
                "value_summary": data,
                "source_reference": reference,
                "limitations": limitations or [],
            }
        }

    def _keyword_set(self, s, p, set_id=None):
        ks = (
            s.get(KeywordSet, set_id)
            if set_id
            else s.scalar(
                select(KeywordSet)
                .where(KeywordSet.site_id == p["id"], KeywordSet.status == "active")
                .order_by(KeywordSet.created_at)
                .limit(1)
            )
        )
        if set_id and (not ks or ks.site_id != p["id"]):
            fail("ai_scope_violation", "Bộ từ khóa không thuộc website này.", 403)
        return ks

    def _profile(self, s, ks, id=None):
        profile = (
            s.get(SearchProfile, id)
            if id
            else s.scalar(
                select(SearchProfile)
                .where(SearchProfile.keyword_set_id == ks.id)
                .order_by(SearchProfile.created_at)
                .limit(1)
            )
        )
        if not profile or profile.keyword_set_id != ks.id:
            fail("ai_scope_violation", "Search Profile không thuộc bộ từ khóa.", 403)
        return profile

    def _execute(self, name, args, p):
        if name in RESEARCH_SPECS:
            return research_execute(self, name, args, p)
        db = self.db
        if name in ("get_project_context", "get_data_source_status"):
            data = context(db, p["id"])
            return self.evidence(
                p,
                "workspace_context",
                data,
                record=p["id"],
                reference="/ai-workspace?project=" + quote(p["id"], safe=""),
                completeness="availability_only",
                limitations=data["limitations"],
            )
        if name in (
            "get_gsc_overview",
            "compare_gsc_periods",
            "get_gsc_top_pages",
            "get_gsc_top_queries",
            "get_gsc_query_page_data",
        ):
            provider = analytics(db, p, args.days, args.end_date)
            if not provider:
                return self.evidence(
                    p,
                    "GSC",
                    {
                        "available": False,
                        "reason": "Chưa có GSC đã kết nối/active cho website này.",
                    },
                    limitations=["Không thay nguồn thật thiếu dữ liệu bằng demo."],
                )
            key = p["property_id"] or p["id"]
            o = provider.overview(key, args.days)
            if (
                args.end_date
                and p["source_type"] == "mock"
                and args.end_date != o.period.end
            ):
                fail("ai_demo_period", "Demo chỉ có kỳ kết thúc ở ngày dataset demo.")
            data = o.model_dump(mode="json")
            source = (
                "demo_gsc"
                if p["source_type"] == "mock"
                else "fixture_gsc" if p["source_type"] == "fixture" else "GSC"
            )
            ref = (
                "/gsc-analytics?site="
                + quote(key, safe="")
                + "&start="
                + str(o.period.start)
                + "&end="
                + str(o.period.end)
            )
            if p["source_type"] == "mock":
                ref = "/?site=" + quote(key, safe="") + "&days=" + str(args.days)
            if name in ("get_gsc_top_pages", "get_gsc_top_queries"):
                dimension = "page" if name.endswith("pages") else "query"
                if p["source_type"] == "mock":
                    report = provider.dimensions(
                        key, args.days, "page_id" if dimension == "page" else "query_id"
                    )
                    rows = [
                        r for r in report.rows if args.search.lower() in r.label.lower()
                    ]
                    if args.sort == "click_change_pct":
                        rows = sorted(
                            rows,
                            key=lambda r: (
                                r.click_change_pct is None,
                                (
                                    r.click_change_pct
                                    if r.click_change_pct is not None
                                    else 0
                                ),
                            ),
                        )
                    else:
                        rows = sorted(
                            rows,
                            key=lambda r: getattr(r.metrics, args.sort),
                            reverse=True,
                        )
                    report = report.model_copy(update={"rows": rows[: args.limit]})
                else:
                    report = provider.dimensions(
                        key,
                        args.days,
                        dimension,
                        page_size=args.limit,
                        search=args.search,
                        sort=args.sort,
                        direction="asc" if args.sort == "click_change_pct" else "desc",
                    )
                data = report.model_dump(mode="json")
                ref += (
                    "&tab=" + ("pages" if dimension == "page" else "queries")
                    if p["source_type"] != "mock"
                    else ""
                )
                for row in data["rows"]:
                    if row.get("current_available") is False:
                        row["metrics"] = None
                    if row.get("previous_available") is False:
                        row["previous"] = None
                for row in data["rows"]:
                    for metric_key in ("metrics", "previous"):
                        if (
                            row.get(metric_key)
                            and row[metric_key].get("impressions") == 0
                        ):
                            row[metric_key]["position"] = None
                            row[metric_key]["ctr"] = None
                data["report_period"] = {
                    "start": str(o.period.start),
                    "end": str(o.period.end),
                }
            elif name == "get_gsc_query_page_data":
                with db.session() as s:
                    kw = s.get(TrackedKeyword, args.keyword_id)
                    if not kw or not self._keyword_set(s, p, kw.keyword_set_id):
                        fail("ai_scope_violation", "Keyword không thuộc website.", 403)
                    row = s.scalar(
                        select(KeywordMetric).where(
                            KeywordMetric.keyword_id == kw.id,
                            KeywordMetric.scope == "page",
                            KeywordMetric.date_start == o.period.start.isoformat(),
                            KeywordMetric.date_end == o.period.end.isoformat(),
                            KeywordMetric.data["keyword_text"].as_string()
                            == kw.keyword_text,
                            KeywordMetric.data["target_url"].as_string()
                            == kw.target_url,
                        )
                    )
                    data = {
                        "available": bool(row),
                        "keyword": kw.keyword_text,
                        "target_url": kw.target_url,
                        "metrics": row.data if row else None,
                        "fetched_at": row.fetched_at if row else None,
                    }
                return self.evidence(
                    p,
                    source,
                    data,
                    record=row.id if row else None,
                    scope="exact_query_target_page/byPage",
                    start=o.period.start,
                    end=o.period.end,
                    collected=row.fetched_at if row else None,
                    reference="/keyword-tracking?site="
                    + quote(p["id"], safe="")
                    + "&set="
                    + kw.keyword_set_id,
                    limitations=[
                        "Chỉ đọc cache query × page đã sync riêng, không ghép query/page totals."
                    ],
                )
            if name in ("get_gsc_overview", "compare_gsc_periods"):
                if not o.has_data:
                    data["current"] = None
                if not o.comparison_available:
                    data["previous"] = None
                for metric_key in ("current", "previous"):
                    if (
                        data.get(metric_key)
                        and data[metric_key].get("impressions") == 0
                    ):
                        data[metric_key]["position"] = None
                        data[metric_key]["ctr"] = None
            return self.evidence(
                p,
                source,
                data,
                record=key,
                scope=(
                    "site/byProperty"
                    if name in ("get_gsc_overview", "compare_gsc_periods")
                    else "page/byPage" if name.endswith("pages") else "query/byProperty"
                ),
                start=o.period.start,
                end=o.period.end,
                collected=str(o.last_updated),
                reference=ref,
                completeness=(
                    "demo_complete"
                    if p["source_type"] == "mock"
                    else (
                        "complete_site_period"
                        if o.comparison_available
                        else "partial_or_missing"
                    )
                ),
                limitations=(
                    ["Dữ liệu mô phỏng, không phản ánh website thật."]
                    if p["source_type"] == "mock"
                    else [
                        *o.warnings,
                        "Rows chi tiết có thể bị privacy/row limits; không dùng tổng rows thay site KPI.",
                    ]
                ),
            )
        if name in (
            "get_technical_audit_summary",
            "get_technical_findings",
            "get_url_diagnostics",
            "get_internal_link_summary",
        ):
            run = audit_run(db, p, args.audit_id)
            if not run:
                return self.evidence(
                    p,
                    "Technical Crawl",
                    {"available": False, "reason": "Chưa có snapshot audit phù hợp."},
                    limitations=["Không có audit không có nghĩa website không có lỗi."],
                )
            ref = f"/technical-seo?project={run.project_id}&audit={run.id}"
            if name == "get_technical_audit_summary":
                data = {
                    "audit_id": run.id,
                    "status": run.status,
                    "summary": run.summary,
                    "coverage": run.coverage,
                }
            elif name == "get_technical_findings":
                report = technical_reports.list_issues(
                    db,
                    run.id,
                    page_size=args.limit,
                    search=args.search,
                    severity=args.severity,
                )
                data = {
                    "total": report["total"],
                    "rows": [
                        {
                            k: r[k]
                            for k in (
                                "id",
                                "url",
                                "rule_id",
                                "title",
                                "severity",
                                "confidence",
                                "evidence_type",
                                "recommendation",
                                "verification",
                                "priority",
                            )
                        }
                        for r in report["rows"]
                    ],
                }
                ref += "&tab=issues"
            elif name == "get_url_diagnostics":
                if not args.url.startswith(("http://", "https://")):
                    fail("ai_invalid_url", "Chỉ tra cứu URL HTTP/HTTPS đã lưu.")
                with db.session() as s:
                    item = s.scalar(
                        select(AuditURL).where(
                            AuditURL.audit_id == run.id, AuditURL.url == args.url
                        )
                    )
                if not item:
                    data = {
                        "available": False,
                        "reason": "URL không có trong snapshot này; không tự crawl.",
                    }
                else:
                    data = {
                        "available": True,
                        **{
                            k: getattr(item, k)
                            for k in (
                                "id",
                                "url",
                                "status_code",
                                "title",
                                "indexability",
                                "depth",
                                "inbound",
                                "outbound",
                                "crawled_at",
                            )
                        },
                        "google_index_status": None,
                    }
                    ref += "&tab=urls&url=" + item.id
            else:
                with db.session() as s:
                    q = select(
                        AuditLink.target_url, func.count().label("observed_links")
                    ).where(AuditLink.audit_id == run.id, AuditLink.internal.is_(True))
                    if args.search:
                        q = q.where(
                            AuditLink.target_url.icontains(args.search, autoescape=True)
                        )
                    records = s.execute(
                        q.group_by(AuditLink.target_url)
                        .order_by(func.count().desc())
                        .limit(10)
                    ).all()
                data = {
                    "rows": [{"url": r[0], "observed_links": r[1]} for r in records],
                    "complete": run.coverage.get("complete", False),
                    "audit_id": run.id,
                }
                ref += "&tab=links"
            return self.evidence(
                p,
                "Technical Crawl",
                data,
                record=run.id,
                scope="stored_HTTP_snapshot",
                collected=run.started_at,
                reference=ref,
                completeness=(
                    "completed_crawl_scope"
                    if run.status == "completed" and run.coverage.get("complete")
                    else "partial_crawl"
                ),
                limitations=[
                    "Bằng chứng chỉ ở thời điểm crawl và phạm vi đã cấu hình; không chứng minh nguyên nhân traffic hoặc trạng thái Google index."
                ],
            )
        if name == "get_keyword_tracking_summary":
            with db.session() as s:
                ks = self._keyword_set(s, p, args.set_id)
                if not ks:
                    return self.evidence(
                        p,
                        "Keyword Tracking",
                        {"available": False, "reason": "Chưa có bộ từ khóa."},
                    )
                profile = self._profile(s, ks, args.profile_id)
                week = args.week or max(
                    1,
                    min(
                        520,
                        (
                            datetime.now(ZoneInfo(ks.timezone)).date()
                            - date.fromisoformat(ks.start_date)
                        ).days
                        // 7
                        + 1,
                    ),
                )
                start, end = keyword_reports.period()
                data = keyword_reports.overview(
                    s, ks, profile.id, week, start, end, "property"
                )
                records = s.execute(
                    keyword_reports.query_rows(
                        s,
                        ks.id,
                        profile.id,
                        week,
                        start,
                        end,
                        sort="change",
                        direction="asc",
                    ).limit(6)
                ).all()
                data["keywords"] = []
                for row in [
                    keyword_reports.row_view(s, r, ks, "property") for r in records
                ]:
                    current = row["current"]
                    data["keywords"].append(
                        {
                            k: row[k]
                            for k in ("id", "keyword_text", "target_url", "change")
                        }
                        | {
                            "current": (
                                {
                                    k: current[k]
                                    for k in (
                                        "rank_status",
                                        "rank_value",
                                        "checked_at",
                                        "timestamp_precision",
                                        "match_mode",
                                    )
                                }
                                if current
                                else None
                            )
                        }
                    )
                data.update(
                    set_id=ks.id,
                    set_name=ks.name,
                    profile_name=profile.name,
                    profile=profile.config,
                    week=week,
                    timezone=ks.timezone,
                )
            return self.evidence(
                p,
                "Keyword Tracking",
                data,
                record=ks.id,
                scope="MANUAL/week/profile",
                reference=f'/keyword-tracking?site={quote(p["id"],safe="")}&set={ks.id}&profile={profile.id}&week={week}&tab=overview',
                completeness="stored_manual_checks",
                limitations=[
                    "NA khác chưa kiểm tra; chỉ so hai tuần liền nhau cùng phép đo. GSC Position không phải rank thủ công."
                ],
            )
        if name == "get_keyword_rank_history":
            with db.session() as s:
                kw = s.get(TrackedKeyword, args.keyword_id)
                if not kw:
                    fail("ai_scope_violation", "Keyword không thuộc website.", 403)
                ks = self._keyword_set(s, p, kw.keyword_set_id)
                profile = self._profile(s, ks, args.profile_id)
                latest = keyword_reports.latest_query(profile.id)
                rows = s.execute(
                    select(RankObservation, TrackingWeek.week_number)
                    .join(latest, latest.c.last_id == RankObservation.id)
                    .join(
                        TrackingWeek,
                        TrackingWeek.id == RankObservation.tracking_week_id,
                    )
                    .where(RankObservation.tracked_keyword_id == kw.id)
                    .order_by(TrackingWeek.week_number.desc())
                    .limit(35)
                ).all()
                data = {
                    "keyword_id": kw.id,
                    "keyword": kw.keyword_text,
                    "target_url": kw.target_url,
                    "profile": profile.config,
                    "rows": [
                        {
                            "week": n,
                            "rank_status": o.rank_status,
                            "rank_value": o.rank_value,
                            "checked_at": o.checked_at,
                            "timestamp_precision": o.timestamp_precision,
                            "target_url_snapshot": o.target_url_snapshot,
                            "match_mode": o.match_mode,
                            "profile_snapshot": o.profile_snapshot,
                            "series_key": o.series_key,
                        }
                        for o, n in reversed(rows[:10])
                    ],
                    "limited_to_latest_weeks": 10,
                }
            return self.evidence(
                p,
                "Keyword Tracking",
                data,
                record=kw.id,
                scope="MANUAL/week/profile",
                reference=f'/keyword-tracking?site={quote(p["id"],safe="")}&set={ks.id}&profile={profile.id}',
                completeness="stored_manual_checks",
                limitations=[
                    "Lịch sử đại diện tuần; không nối chuỗi khác profile/URL/mode, không gán NA=101 hoặc chưa kiểm tra=0."
                ],
            )
        fail("ai_tool_not_allowed", "Tool chưa được triển khai.", 403)
