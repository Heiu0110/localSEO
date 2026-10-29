"""Transactional research imports and review. Source SEO services remain read-only."""

import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy import select, func
from app.ai.common import uid, now, view, fail, require, redact
from app.ai.context import project as local_project, analytics, audit_run
from app.keywords.core import normalize, safe_url, create_keyword
from app.keywords.schemas import KeywordInput
from app.keywords.models import KeywordSet, KeywordGroup, TrackedKeyword
from app.technical.models import AuditURL
from .models import *
from .schemas import Candidate, MetricInput, ClusterInput

LIMITATIONS = [
    "GSC impressions không phải search volume; chi tiết queries có thể thiếu.",
    "SERP chỉ phản ánh mẫu được nhập, không phải thị phần toàn thị trường.",
    "Topical Map và provider trả phí chưa kết nối; không tự fetch URL hoặc gọi AI.",
]


def scoped(s, model, id, project_id):
    obj = require(s, model, id)
    if obj.project_id != project_id:
        fail("research_scope", "Dữ liệu thuộc dự án Research khác.", 403)
    return obj


def event(s, pid, typ, id, decision, data):
    s.add(
        ResearchReview(
            id=uid(),
            project_id=pid,
            entity_type=typ,
            entity_id=id,
            decision=decision,
            data=redact(data),
            created_at=now(),
        )
    )


def project_view(s, p):
    return {
        **view(p),
        "keyword_count": s.scalar(
            select(func.count())
            .select_from(ResearchKeyword)
            .where(ResearchKeyword.project_id == p.id)
        ),
        "snapshot_count": s.scalar(
            select(func.count())
            .select_from(SerpSnapshot)
            .where(SerpSnapshot.project_id == p.id)
        ),
    }


def new_project(s, db, data):
    if data.local_project_id:
        local_project(db, data.local_project_id)
    if s.scalar(select(func.count()).select_from(ResearchProject)) >= 100:
        fail("research_limit", "Tối đa 100 dự án Research.", 409)
    p = ResearchProject(
        id=uid(),
        **data.model_dump(),
        status="active",
        settings={
            "min_impressions": 100,
            "low_ctr": 0.02,
            "near_min": 8,
            "near_max": 20,
        },
        created_at=now(),
        updated_at=now(),
    )
    s.add(p)
    s.flush()
    return p


def writable(p):
    if p.status != "active":
        fail("research_archived", "Mở lại dự án trước khi thay đổi dữ liệu.", 409)


def sources(s, ids):
    result = {k: [] for k in ids}
    if not ids:
        return result
    all_sources = list(
        s.scalars(
            select(ResearchSource)
            .where(ResearchSource.keyword_id.in_(ids))
            .order_by(ResearchSource.collected_at.desc(), ResearchSource.id)
        )
    )
    metrics = {}
    for m in s.scalars(
        select(ResearchMetric)
        .join(ResearchSource, ResearchSource.id == ResearchMetric.source_id)
        .where(ResearchSource.keyword_id.in_(ids))
    ):
        metrics.setdefault(m.source_id, []).append(
            {
                "metric_type": m.metric_type,
                "value": m.value,
                "unit": m.unit,
                "scope": m.scope,
                "reporting_start": m.reporting_start,
                "reporting_end": m.reporting_end,
                "metadata": m.metadata_json,
            }
        )
    for src in all_sources:
        result[src.keyword_id].append({**view(src), "metrics": metrics.get(src.id, [])})
    return result


def keyword_views(s, rows):
    src = sources(s, [k.id for k in rows])
    return [{**view(k), "sources": src[k.id]} for k in rows]


def preview(s, p, rows, kind="keywords", extra=None):
    writable(p)
    if not rows:
        fail(
            "research_no_data",
            "Không có dữ liệu phù hợp; không thay bằng dữ liệu demo.",
            409,
        )
    if len(rows) > 1000:
        fail("research_limit", "Mỗi lượt nhập tối đa 1.000 dòng.")
    if (
        s.scalar(
            select(func.count())
            .select_from(ResearchJob)
            .where(ResearchJob.project_id == p.id, ResearchJob.status == "preview")
        )
        >= 100
    ):
        fail(
            "research_limit",
            "Tối đa 100 bản xem trước chưa xử lý trong mỗi dự án.",
            409,
        )
    data = redact({"rows": rows, **(extra or {})})
    job = ResearchJob(
        id=uid(),
        project_id=p.id,
        kind=kind,
        status="preview",
        data=data,
        created_at=now(),
    )
    s.add(job)
    s.flush()
    return view(job)


def discover(db, s, p, data):
    rows = []
    limitations = []
    locale = {"country": p.country, "language": p.language}
    if data.source == "seed":
        rows = [
            Candidate(keyword_text=t, **locale).model_dump(mode="json")
            for t in data.text.splitlines()
            if t.strip()
        ]
    elif data.source == "rows":
        rows = [r.model_dump(mode="json") for r in data.rows]
    else:
        if not p.local_project_id:
            fail(
                "research_no_website",
                "Dự án độc lập chưa gắn website; hãy nhập seed/tệp.",
                409,
            )
        site = local_project(db, p.local_project_id)
        if data.source == "gsc":
            provider = analytics(db, site, data.days, data.end_date)
            if not provider:
                fail("research_no_gsc", "Website chưa có GSC đã lưu.", 409)
            key = site["property_id"] or site["id"]
            overview = provider.overview(key, data.days)
            if site["source_type"] == "mock":
                if data.end_date and str(data.end_date) != str(overview.period.end):
                    fail("research_demo_period", "Demo dùng ngày cuối dataset.")
                report = provider.dimensions(key, data.days, "query_id")
                raw = [r.model_dump(mode="json") for r in report.rows]
            else:
                raw = []
                for page in range(1, 11):
                    report = provider.dimensions(
                        key,
                        data.days,
                        "query",
                        page=page,
                        page_size=100,
                        search=data.search,
                    )
                    raw.extend(r.model_dump(mode="json") for r in report.rows)
                    if len(report.rows) < 100:
                        break
            for r in raw:
                m = r["metrics"] if r.get("current_available", True) else None
                if m and m["impressions"]:
                    m = {**m, "ctr": m["clicks"] / m["impressions"]}
                if (
                    not m
                    or not m["impressions"]
                    or data.search.casefold() not in r["label"].casefold()
                ):
                    continue
                if (
                    m["impressions"] < data.min_impressions
                    or m["clicks"] < data.min_clicks
                    or m["ctr"] > data.max_ctr
                    or not data.min_position <= m["position"] <= data.max_position
                ):
                    continue
                metrics = [
                    MetricInput(
                        metric_type="gsc_" + k,
                        value=m[k],
                        unit=u,
                        scope="query/byProperty/web/all_countries/all_devices",
                        metadata={
                            "country_scope": "all_countries",
                            "device_scope": "all_devices",
                        },
                        reporting_start=overview.period.start,
                        reporting_end=overview.period.end,
                    ).model_dump(mode="json")
                    for k, u in [
                        ("clicks", "clicks"),
                        ("impressions", "impressions"),
                        ("ctr", "ratio"),
                        ("position", "average_position"),
                    ]
                ]
                rows.append(
                    Candidate(
                        keyword_text=r["label"],
                        provider=(
                            "demo_gsc"
                            if site["source_type"] == "mock"
                            else (
                                "fixture_gsc"
                                if site["source_type"] == "fixture"
                                else "GSC"
                            )
                        ),
                        method="stored_gsc_query",
                        reference=key,
                        collected_at=overview.last_synced_at or overview.last_updated,
                        metrics=metrics,
                        **locale,
                    ).model_dump(mode="json")
                )
            limitations = [
                "Tối đa 1.000 query rows đã lưu; Google có thể ẩn/giới hạn query. Không suy ra URL từ cube page độc lập.",
                "Ngày thu thập nguồn xem tại GSC; imported_at không làm dữ liệu cũ thành dữ liệu hiện tại.",
            ]
        elif data.source == "tracking":
            ks = require(s, KeywordSet, data.set_id or "")
            if ks.site_id != p.local_project_id:
                fail("research_scope", "Bộ tracking không thuộc website này.", 403)
            q = select(TrackedKeyword).where(TrackedKeyword.keyword_set_id == ks.id)
            if data.group_id:
                group = require(s, KeywordGroup, data.group_id)
                if group.keyword_set_id != ks.id:
                    fail("research_scope", "Nhóm không thuộc bộ từ khóa.", 403)
                q = q.where(TrackedKeyword.group_id == group.id)
            for k in s.scalars(q.order_by(TrackedKeyword.id).limit(data.limit)):
                group = s.get(KeywordGroup, k.group_id) if k.group_id else None
                rows.append(
                    Candidate(
                        keyword_text=k.keyword_text,
                        provider="Keyword Tracking",
                        method="stored_tracking",
                        reference=k.id,
                        target_url=k.target_url,
                        group_name=group.name if group else "",
                        metadata={
                            "set_id": ks.id,
                            "priority": k.priority,
                            "mapping_kind": "tracking_existing",
                        },
                        **locale,
                    ).model_dump(mode="json")
                )
        elif data.source == "crawl":
            run = audit_run(db, site)
            if not run:
                fail("research_no_crawl", "Chưa có audit thuộc website này.", 409)
            for u in s.scalars(
                select(AuditURL)
                .where(AuditURL.audit_id == run.id)
                .order_by(AuditURL.id)
                .limit(data.limit)
            ):
                if u.title:
                    rows.append(
                        Candidate(
                            keyword_text=u.title[:500],
                            provider="Technical Crawl",
                            method="title_heuristic",
                            reference=u.id,
                            target_url=u.url,
                            collected_at=u.crawled_at or run.started_at,
                            notes="Ứng viên từ title, không phải Google demand.",
                            **locale,
                        ).model_dump(mode="json")
                    )
    rows = rows[: data.limit]
    seen = set()
    existing = {
        (x.normalized_keyword, x.country, x.language)
        for x in s.scalars(
            select(ResearchKeyword).where(ResearchKeyword.project_id == p.id)
        )
    }
    duplicates = 0
    for r in rows:
        key = (normalize(r["keyword_text"]), r["country"], r["language"])
        r["duplicate"] = key in seen or key in existing
        duplicates += int(r["duplicate"])
        seen.add(key)
    return preview(
        s,
        p,
        rows,
        extra={
            "duplicates": duplicates,
            "limitations": limitations,
            "source": data.source,
        },
    )


def commit_keywords(s, p, job):
    created = 0
    observations = 0
    for raw in job.data["rows"]:
        data = Candidate.model_validate(
            {k: v for k, v in raw.items() if k != "duplicate"}
        )
        norm = normalize(data.keyword_text)
        k = s.scalar(
            select(ResearchKeyword).where(
                ResearchKeyword.project_id == p.id,
                ResearchKeyword.normalized_keyword == norm,
                ResearchKeyword.country == data.country,
                ResearchKeyword.language == data.language,
            )
        )
        if not k:
            if (
                s.scalar(
                    select(func.count())
                    .select_from(ResearchKeyword)
                    .where(ResearchKeyword.project_id == p.id)
                )
                >= 5000
            ):
                fail("research_limit", "Dự án tối đa 5.000 từ khóa.")
            k = ResearchKeyword(
                id=uid(),
                project_id=p.id,
                keyword_text=data.keyword_text,
                normalized_keyword=norm,
                country=data.country,
                language=data.language,
                group_name=data.group_name,
                intent=data.intent,
                target_url=data.target_url,
                mapping_status="suggested" if data.target_url else "undecided",
                brand_label="unknown",
                notes=data.notes,
                status="draft",
                cluster_id=None,
                created_at=now(),
                updated_at=now(),
            )
            s.add(k)
            s.flush()
            created += 1
        identity = hashlib.sha256(
            json.dumps(
                data.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
            ).encode()
        ).hexdigest()
        if s.scalar(
            select(ResearchSource.id).where(
                ResearchSource.keyword_id == k.id, ResearchSource.identity == identity
            )
        ):
            continue
        if (
            s.scalar(
                select(func.count())
                .select_from(ResearchSource)
                .where(ResearchSource.keyword_id == k.id)
            )
            >= 100
        ):
            fail("research_limit", "Mỗi keyword tối đa 100 source observations.")
        src = ResearchSource(
            id=uid(),
            keyword_id=k.id,
            identity=identity,
            provider=data.provider,
            method=data.method,
            reference=data.reference,
            original_text=data.keyword_text,
            seed=data.seed,
            collected_at=(
                data.collected_at.isoformat() if data.collected_at else job.created_at
            ),
            data={
                "version": 1,
                "imported_at": job.created_at,
                "metadata": data.metadata,
                "availability": "supplied" if data.metrics else "no_demand_metrics",
            },
        )
        s.add(src)
        s.flush()
        observations += 1
        for m in data.metrics:
            s.add(
                ResearchMetric(
                    id=uid(),
                    source_id=src.id,
                    metric_type=m.metric_type,
                    value=m.value,
                    unit=m.unit,
                    scope=m.scope,
                    reporting_start=(
                        str(m.reporting_start) if m.reporting_start else None
                    ),
                    reporting_end=str(m.reporting_end) if m.reporting_end else None,
                    metadata_json=m.metadata,
                )
            )
    return {
        "created": created,
        "skipped": len(job.data["rows"]) - created,
        "source_observations_added": observations,
    }


def patch_keyword(s, p, k, changes):
    writable(p)
    before = view(k)
    values = changes.model_dump(exclude_unset=True)
    if any(v is None for key, v in values.items() if key != "cluster_id"):
        fail("research_validation", "Không được ghi null cho trường này.")
    if values.get("cluster_id"):
        scoped(s, ResearchCluster, values["cluster_id"], p.id)
    if values.get("mapping_status", k.mapping_status) in (
        "approved",
        "planned",
    ) and not values.get("target_url", k.target_url):
        fail("research_mapping", "Mapping cần URL đích.")
    for key, v in values.items():
        setattr(k, key, v)
    k.updated_at = now()
    if before["cluster_id"] != k.cluster_id and before["cluster_id"]:
        old = s.get(ResearchCluster, before["cluster_id"])
        if old:
            old.status = "needs_review"
            if old.primary_keyword_id == k.id:
                old.primary_keyword_id = None
    if k.cluster_id:
        assigned = s.get(ResearchCluster, k.cluster_id)
        assigned.status = "needs_review"
    event(s, p.id, "keyword", k.id, k.status, {"before": before, "after": view(k)})


def create_cluster(s, p, data, evidence=None):
    writable(p)
    if (
        s.scalar(
            select(func.count())
            .select_from(ResearchCluster)
            .where(ResearchCluster.project_id == p.id)
        )
        >= 500
    ):
        fail("research_limit", "Tối đa 500 cluster mỗi dự án.")
    members = [
        scoped(s, ResearchKeyword, id, p.id) for id in dict.fromkeys(data.keyword_ids)
    ]
    if data.primary_keyword_id and data.primary_keyword_id not in data.keyword_ids:
        fail("research_primary", "Primary keyword cần thuộc cluster.")
    if data.mapping_status in ("approved", "planned") and not data.target_url:
        fail("research_mapping", "Mapping cần URL đích.")
    c = ResearchCluster(
        id=uid(),
        project_id=p.id,
        **data.model_dump(exclude={"keyword_ids"}),
        status="draft",
        evidence=evidence or {"method": "manual", "confidence": "user_defined"},
        created_at=now(),
        updated_at=now(),
    )
    s.add(c)
    s.flush()
    for k in members:
        if k.cluster_id:
            old = s.get(ResearchCluster, k.cluster_id)
            if old:
                old.status = "needs_review"
                if old.primary_keyword_id == k.id:
                    old.primary_keyword_id = None
        k.cluster_id = c.id
        k.updated_at = now()
    event(
        s,
        p.id,
        "cluster",
        c.id,
        "draft",
        {"proposal": view(c), "keyword_ids": data.keyword_ids},
    )
    return c


def intent_suggestion(k):
    text = k.normalized_keyword
    tests = [
        ("informational", ["cách ", "là gì", "hướng dẫn", "how to"]),
        ("local", ["gần đây", "near me", "tại hà nội", "tphcm"]),
        ("transactional", ["mua ", "đặt hàng", "báo giá"]),
        ("commercial", ["xưởng", "so sánh", "review", "tốt nhất"]),
    ]
    matches = [i for i, words in tests if any(w in text for w in words)]
    intent = matches[0] if len(matches) == 1 else "mixed" if matches else "unknown"
    return {
        "intent": intent,
        "method": "modifier_heuristic_v1",
        "confidence": "low",
        "status": "draft",
        "reason": (
            "Tín hiệu từ modifier: " + ", ".join(matches)
            if matches
            else "Không đủ modifier rõ ràng."
        ),
        "evidence": [k.id],
        "limitations": "Không phải kết luận intent từ SERP; phân loại thủ công có thẩm quyền.",
    }


def transfer_preview(s, p, data):
    writable(p)
    ks = require(s, KeywordSet, data.set_id)
    if not p.local_project_id or ks.site_id != p.local_project_id:
        fail("research_scope", "Chỉ chuyển vào bộ của đúng website đã gắn.", 403)
    if ks.status != "active":
        fail("research_tracking_archived", "Bộ tracking đã lưu trữ.", 409)
    group = s.get(KeywordGroup, data.group_id) if data.group_id else None
    if data.group_id and (not group or group.keyword_set_id != ks.id):
        fail("research_scope", "Nhóm không thuộc bộ đích.", 403)
    rows = []
    seen = set()
    for id in dict.fromkeys(data.keyword_ids):
        k = scoped(s, ResearchKeyword, id, p.id)
        if k.status != "approved":
            fail("research_not_approved", "Chỉ chuyển từ khóa đã duyệt.", 409)
        duplicate = s.scalar(
            select(TrackedKeyword).where(
                TrackedKeyword.keyword_set_id == ks.id,
                TrackedKeyword.normalized_keyword == k.normalized_keyword,
            )
        )
        rows.append(
            {
                "id": k.id,
                "keyword_text": k.keyword_text,
                "country": k.country,
                "language": k.language,
                "intent": k.intent,
                "updated_at": k.updated_at,
                "status": k.status,
                "target_url": k.target_url if k.mapping_status == "approved" else "",
                "group_id": data.group_id,
                "group_name": group.name if group else "",
                "action": (
                    "skip"
                    if duplicate
                    else (
                        "skip_selection_duplicate"
                        if k.normalized_keyword in seen
                        else "create"
                    )
                ),
                "existing_id": duplicate.id if duplicate else None,
                "existing_target_url": duplicate.target_url if duplicate else None,
            }
        )
        seen.add(k.normalized_keyword)
    return preview(
        s,
        p,
        rows,
        "tracking_transfer",
        {
            "set_id": ks.id,
            "site_id": ks.site_id,
            "group_id": data.group_id,
            "limitations": [
                "Chỉ thêm mới; trùng được bỏ qua, không sửa URL, nhóm hoặc rank cũ.",
                "Locale được giữ trong ghi chú Research; Search Profile vẫn do bạn quản lý ở Tracking.",
            ],
        },
    )


def commit_transfer(s, p, job):
    ks = require(s, KeywordSet, job.data["set_id"])
    if ks.site_id != p.local_project_id or ks.status != "active":
        fail("research_scope", "Bộ tracking đã đổi/ngừng hoạt động.", 409)
    group = job.data["group_id"]
    if group and require(s, KeywordGroup, group).keyword_set_id != ks.id:
        fail("research_scope", "Nhóm đích đã đổi.", 409)
    created = skipped = 0
    created_norms = set()
    for row in job.data["rows"]:
        k = scoped(s, ResearchKeyword, row["id"], p.id)
        if k.status != "approved" or k.updated_at != row["updated_at"]:
            fail("research_preview_stale", "Từ khóa đã đổi; hãy xem trước lại.", 409)
        if row["action"] == "skip_selection_duplicate":
            if k.normalized_keyword not in created_norms:
                fail(
                    "research_preview_stale",
                    "Lựa chọn trùng đã đổi; hãy xem trước lại.",
                    409,
                )
            skipped += 1
            continue
        duplicate = s.scalar(
            select(TrackedKeyword).where(
                TrackedKeyword.keyword_set_id == ks.id,
                TrackedKeyword.normalized_keyword == k.normalized_keyword,
            )
        )
        if (duplicate.id if duplicate else None) != row["existing_id"]:
            fail("research_preview_stale", "Tracking đã đổi; hãy xem trước lại.", 409)
        if duplicate:
            skipped += 1
            continue
        create_keyword(
            s,
            KeywordInput(
                keyword_set_id=ks.id,
                keyword_text=k.keyword_text,
                group_id=group,
                target_url=row["target_url"],
                search_intent=k.intent,
                notes=f"Research {p.id}/{k.id}; locale {k.country}/{k.language}",
            ),
        )
        created += 1
        created_norms.add(k.normalized_keyword)
    return {
        "created": created,
        "skipped": skipped,
        "updated": 0,
        "rank_observations_written": 0,
    }


def commit_job(s, p, job, confirm):
    if not confirm:
        fail("research_confirmation", "Cần xác nhận bản xem trước.", 409)
    writable(p)
    if job.status == "committed":
        return job.data["result"]
    if job.status != "preview":
        fail("research_job", "Bản xem trước không còn hợp lệ.", 409)
    if job.kind == "keywords":
        result = commit_keywords(s, p, job)
    elif job.kind == "tracking_transfer":
        result = commit_transfer(s, p, job)
    elif job.kind == "serp":
        from .serp import save_snapshot

        result = save_snapshot(s, p, job.data["rows"][0])
    else:
        fail("research_job", "Loại công việc không hỗ trợ.")
    job.status = "committed"
    job.data = {**job.data, "result": result}
    p.updated_at = now()
    event(s, p.id, "import", job.id, "committed", result)
    return result
