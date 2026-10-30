"""Small immutable evidence snapshots referencing source systems, not copies of datasets."""

from datetime import datetime, timezone
from sqlalchemy import select
from app.ai.common import now, uid, view
from app.ai.context import project as local_project, audit_run, analytics
from app.technical.models import AuditURL, AuditIssue, AuditLink
from app.research.models import ResearchKeyword, ResearchCluster
from app.keywords.models import TrackedKeyword
from .models import VisibilityEvidence
from . import core, extraction


def put(s, pid, kind, id, data, reference=None):
    snapshot = {
        "source_type": kind,
        "source_id": id,
        "value": data,
        "source_reference": reference,
    }
    signature = core.digest(snapshot)
    row = s.scalar(
        select(VisibilityEvidence).where(
            VisibilityEvidence.project_id == pid,
            VisibilityEvidence.source_type == kind,
            VisibilityEvidence.source_id == id,
            VisibilityEvidence.signature == signature,
        )
    )
    if not row:
        row = VisibilityEvidence(
            id=uid(),
            project_id=pid,
            source_type=kind,
            source_id=id,
            signature=signature,
            data=snapshot,
            created_at=now(),
        )
        s.add(row)
        s.flush()
    return row.id


def observation(s, p, bundle, brand_id):
    row = bundle["observation"]
    from .metrics import confirmed_mentions, citation_eligible, context

    return put(
        s,
        p.id,
        "observation",
        row.id,
        {
            "prompt_id": row.prompt_id,
            "prompt_snapshot": row.prompt_snapshot,
            "response_sha256": core.digest(row.response_text),
            "extraction_id": bundle["extraction"].id if bundle["extraction"] else None,
            "context": context(row),
            "observed_at": row.observed_at,
            "complete": row.completeness == "complete",
            "citation_eligible": citation_eligible(bundle),
            "brand_mention_confirmed": bool(confirmed_mentions(bundle, brand_id)),
            "ambiguous_brand_match": any(
                m["entity_id"] == brand_id
                and m["status"] in ("POSSIBLE_MATCH", "NEEDS_REVIEW")
                for m in bundle["mentions"]
            ),
        },
        f"/ai-visibility?project={p.id}&observation={row.id}",
    )


def linked_urls(s, p, prompt):
    refs = prompt.data
    urls, context = set(), []
    if refs.get("target_url"):
        urls.add(refs["target_url"])
    if refs.get("research_cluster_id"):
        cluster = s.get(ResearchCluster, refs["research_cluster_id"])
        if cluster:
            context.append(
                {
                    "kind": "research_cluster",
                    "id": cluster.id,
                    "name": cluster.name,
                    "target_url": cluster.target_url,
                    "mapping_status": cluster.mapping_status,
                    "status": cluster.status,
                }
            )
            if cluster.target_url and cluster.mapping_status == "approved":
                urls.add(cluster.target_url)
    for id in refs.get("research_keyword_ids", []):
        keyword = s.get(ResearchKeyword, id)
        if keyword:
            context.append(
                {
                    "kind": "research_keyword",
                    "id": id,
                    "keyword": keyword.keyword_text,
                    "target_url": keyword.target_url,
                    "mapping_status": keyword.mapping_status,
                    "status": keyword.status,
                }
            )
            if keyword.target_url and keyword.mapping_status == "approved":
                urls.add(keyword.target_url)
    if refs.get("tracking_keyword_id"):
        keyword = s.get(TrackedKeyword, refs["tracking_keyword_id"])
        if keyword and keyword.target_url:
            urls.add(keyword.target_url)
            context.append(
                {
                    "kind": "tracked_keyword",
                    "id": keyword.id,
                    "keyword": keyword.keyword_text,
                    "target_url": keyword.target_url,
                    "manual_rank_is_not_ai_visibility": True,
                }
            )
    return sorted(urls), context


def seo_context(s, db, p, prompts):
    """Read exact linked URLs only. No live requests, guessed keyword joins or crawling."""
    local = local_project(db, p.local_project_id)
    run = audit_run(db, local)
    url_map, references, missing, technical = {}, [], [], []
    for prompt in prompts:
        urls, related = linked_urls(s, p, prompt)
        url_map[prompt.id] = urls
        for row in related:
            references.append(
                put(
                    s,
                    p.id,
                    row["kind"],
                    row["id"],
                    row,
                    (
                        "/keyword-research"
                        if row["kind"].startswith("research")
                        else "/keyword-tracking"
                    ),
                )
            )
    urls = sorted({url for values in url_map.values() for url in values})[:30]
    if run:
        for url in urls:
            page = s.scalar(
                select(AuditURL).where(AuditURL.audit_id == run.id, AuditURL.url == url)
            )
            if not page:
                continue
            age = None
            try:
                age = max(
                    0,
                    (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(
                            (page.crawled_at or run.started_at).replace("Z", "+00:00")
                        )
                    ).days,
                )
            except (ValueError, TypeError):
                pass
            references.append(
                put(
                    s,
                    p.id,
                    "audit_url",
                    page.id,
                    {
                        "url": page.url,
                        "audit_id": run.id,
                        "status_code": page.status_code,
                        "indexability": page.indexability,
                        "title": page.title,
                        "inbound": page.inbound,
                        "outbound": page.outbound,
                        "crawled_at": page.crawled_at,
                        "age_days": age,
                        "source_type": local["source_type"],
                    },
                    f"/technical-seo?project={run.project_id}&audit={run.id}",
                )
            )
            for link in s.scalars(
                select(AuditLink)
                .where(
                    AuditLink.audit_id == run.id,
                    AuditLink.source_id == page.id,
                    AuditLink.internal.is_(True),
                )
                .limit(5)
            ):
                references.append(
                    put(
                        s,
                        p.id,
                        "internal_link",
                        str(link.id),
                        {
                            "source_url": page.url,
                            "target_url": link.target_url,
                            "anchor": link.anchor,
                            "audit_id": run.id,
                            "crawled_at": page.crawled_at,
                        },
                        "/technical-seo",
                    )
                )
            for issue in s.scalars(
                select(AuditIssue)
                .where(AuditIssue.audit_id == run.id, AuditIssue.url_id == page.id)
                .order_by(AuditIssue.priority.desc())
                .limit(8)
            ):
                source = {
                    "id": issue.id,
                    "url": page.url,
                    "audit_id": run.id,
                    "rule_id": issue.rule_id,
                    "category": issue.category,
                    "title": issue.title,
                    "severity": issue.severity,
                    "confidence": issue.confidence,
                    "evidence": issue.evidence,
                    "crawled_at": page.crawled_at or run.started_at,
                    "age_days": age,
                    "stale": age is None or age > 30,
                    "source_type": local["source_type"],
                    "causal_link_to_ai_visibility": "unproven",
                }
                eid = put(
                    s,
                    p.id,
                    "technical_issue",
                    issue.id,
                    source,
                    f"/technical-seo?project={run.project_id}&audit={run.id}",
                )
                technical.append({**source, "evidence_id": eid})
    else:
        missing.append(
            "Chưa có Technical Audit liên kết với website; không tự crawl mới."
        )
    provider = analytics(db, local, 28)
    if provider:
        key = local["property_id"] or local["id"]
        report = provider.overview(key, 28)
        if getattr(report, "has_data", True):
            dimensions = provider.dimensions(
                key, 28, "page_id" if local["source_type"] == "mock" else "page"
            )
            for row in dimensions.rows:
                try:
                    normalized = extraction.normalize_url(row.label)
                except ValueError:
                    continue
                if normalized not in urls:
                    continue
                references.append(
                    put(
                        s,
                        p.id,
                        "gsc_page",
                        row.id,
                        {
                            "url": row.label,
                            "metrics": row.metrics.model_dump(),
                            "period": report.period.model_dump(mode="json"),
                            "source_type": local["source_type"],
                            "scope": "stored_by_page_row_not_site_total",
                            "coverage": "bounded_rows",
                            "last_updated": (
                                report.last_updated.isoformat()
                                if hasattr(report.last_updated, "isoformat")
                                else str(report.last_updated)
                            ),
                            "is_ai_visibility_metric": False,
                        },
                        f"/gsc-analytics?site={key}",
                    )
                )
            missing.append(
                "GSC chỉ là dữ liệu Search hiện có; không suy ra AI Overview/AI Mode/Generative AI Performance hoặc query×page chưa lưu."
            )
        else:
            missing.append(
                "Property GSC chưa có dữ liệu đã sync; không thay bằng demo."
            )
    else:
        missing.append("Chưa có GSC đã lưu cho website; không tạo số liệu thay thế.")
    return {
        "url_map": url_map,
        "evidence_ids": list(dict.fromkeys(references)),
        "technical": technical,
        "missing": missing,
        "topical_map_available": False,
    }
