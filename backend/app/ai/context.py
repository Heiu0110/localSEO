from datetime import date, datetime, timezone
from urllib.parse import urlsplit
from sqlalchemy import func, select
from app.db.models import MetricFact, Property
from app.services.dashboard_service import get_service
from app.providers.sqlite_provider import SQLiteAnalyticsProvider
from app.technical.models import AuditProject, AuditRun
from app.keywords.models import KeywordSet
from .common import fail


def host(url):
    try:
        return (
            url.removeprefix("sc-domain:").lower()
            if url.startswith("sc-domain:")
            else urlsplit(url if "://" in url else "https://" + url).hostname
        )
    except ValueError:
        return None


def project(db, key):
    demos = {p.id: p for p in get_service().provider.sites}
    if key in demos:
        return {
            "id": key,
            "name": demos[key].domain,
            "site_url": demos[key].domain,
            "source_type": "mock",
            "property_id": None,
            "technical_id": None,
            "active": True,
        }
    with db.session() as s:
        p = s.get(Property, key)
        if p:
            return {
                "id": key,
                "name": p.display_name,
                "site_url": p.site_url,
                "source_type": p.source_type,
                "property_id": p.id,
                "technical_id": None,
                "active": p.is_active,
            }
        if key.startswith("audit:"):
            p = s.get(AuditProject, key[6:])
            if p:
                return {
                    "id": key,
                    "name": p.name,
                    "site_url": p.root_url,
                    "source_type": p.source_type,
                    "property_id": p.property_id,
                    "technical_id": p.id,
                    "active": True,
                }
    fail("ai_project_not_found", "Website/dự án không còn trong workspace.", 404)


def projects(db):
    result = [project(db, p.id) for p in get_service().provider.sites]
    with db.session() as s:
        props = list(s.scalars(select(Property).order_by(Property.added_at)))
        audits = list(s.scalars(select(AuditProject).order_by(AuditProject.created_at)))
    result.extend(project(db, p.id) for p in props)
    known = {p["property_id"] for p in result if p["property_id"]}
    demo_hosts = {host(p["site_url"]) for p in result if p["source_type"] == "mock"}
    result.extend(
        project(db, "audit:" + p.id)
        for p in audits
        if p.property_id not in known
        and (p.source_type == "fixture" or host(p.root_url) not in demo_hosts)
    )
    return result


def audit_projects(db, p):
    with db.session() as s:
        candidates = list(s.scalars(select(AuditProject)))
    if p["technical_id"]:
        return [x for x in candidates if x.id == p["technical_id"]]
    if p["property_id"]:
        return [x for x in candidates if x.property_id == p["property_id"]]
    return [
        x
        for x in candidates
        if not x.property_id
        and x.source_type == "live"
        and host(x.root_url) == host(p["site_url"])
    ]


def audit_run(db, p, id=None):
    ids = [x.id for x in audit_projects(db, p)]
    if not ids:
        if id:
            fail(
                "ai_scope_violation",
                "Audit không thuộc website của cuộc hội thoại.",
                403,
            )
        return None
    with db.session() as s:
        if id:
            run = s.get(AuditRun, id)
            if not run or run.project_id not in ids:
                fail(
                    "ai_scope_violation",
                    "Audit không thuộc website của cuộc hội thoại.",
                    403,
                )
            return run
        return s.scalar(
            select(AuditRun)
            .where(
                AuditRun.project_id.in_(ids),
                AuditRun.status.in_(["completed", "partial", "cancelled"]),
            )
            .order_by(AuditRun.started_at.desc())
            .limit(1)
        )


def analytics(db, p, days=28, end=None):
    if p["technical_id"] and not p["property_id"]:
        return None
    if p["source_type"] == "mock":
        return get_service()
    if not p["property_id"] or not p["active"]:
        return None
    return SQLiteAnalyticsProvider(db, end=end)


def context(db, key):
    p = project(db, key)
    with db.session() as s:
        dates = (
            s.execute(
                select(func.min(MetricFact.date), func.max(MetricFact.date)).where(
                    MetricFact.property_id == p["property_id"],
                    MetricFact.dataset_type == "site",
                    MetricFact.search_type == "web",
                )
            ).one()
            if p["property_id"]
            else (None, None)
        )
        sets = list(
            s.scalars(
                select(KeywordSet)
                .where(KeywordSet.site_id == key)
                .order_by(KeywordSet.created_at)
                .limit(10)
            )
        )
        count = s.scalar(
            select(func.count())
            .select_from(KeywordSet)
            .where(KeywordSet.site_id == key)
        )
    run = audit_run(db, p)
    if p["source_type"] == "mock":
        dates = (
            get_service().provider.start_date.isoformat(),
            get_service().provider.end_date.isoformat(),
        )
    sources = [
        {
            "id": "gsc",
            "name": "GSC",
            "status": (
                "demo"
                if p["source_type"] == "mock"
                else (
                    "available"
                    if dates[1] and p["active"]
                    else (
                        "inactive"
                        if p["property_id"] and not p["active"]
                        else "not_synced" if p["property_id"] else "not_connected"
                    )
                )
            ),
            "date_start": dates[0],
            "date_end": dates[1],
            "limitations": "Chi tiết query/page có thể thiếu. Tổng traffic dùng site dataset byProperty.",
        },
        {
            "id": "technical",
            "name": "Technical SEO",
            "status": "available" if run else "not_audited",
            "last_collected_at": run.started_at if run else None,
            "audit_id": run.id if run else None,
            "limitations": "Snapshot HTTP/HTML; không có URL Inspection/live rendering.",
        },
        {
            "id": "keywords",
            "name": "Keyword Tracking",
            "status": "available" if sets else "not_configured",
            "total_sets": count,
            "limitations": "Quan sát MANUAL theo profile/tuần, không phải GSC Average Position.",
        },
        {
            "id": "topical",
            "name": "Topical Map",
            "status": "not_implemented",
            "limitations": "Repo chỉ có placeholder; không có dữ liệu/mapping để phân tích.",
        },
    ]
    from app.research.models import ResearchProject

    with db.session() as s:
        research_count = s.scalar(
            select(func.count())
            .select_from(ResearchProject)
            .where(ResearchProject.local_project_id == key)
        )
    sources.append(
        {
            "id": "research",
            "name": "Keyword Research",
            "status": "available" if research_count else "not_configured",
            "limitations": "Dữ liệu đã nhập có nguồn; SERP không phải rank live hoặc thị phần.",
        }
    )
    return {
        "project": p,
        "sources": sources,
        "keyword_sets": [
            {
                "id": x.id,
                "name": x.name,
                "start_date": x.start_date,
                "timezone": x.timezone,
                "status": x.status,
            }
            for x in sets
        ],
        "keyword_set_count": count,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Chỉ dùng dữ liệu SQLite hiện có và demo có nhãn; không tự crawl/sync, không nghiên cứu web trong Phase 6.",
            "Topical Map/Server Logs/URL Inspection chưa có adapter.",
        ],
    }
