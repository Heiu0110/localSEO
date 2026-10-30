"""Cohort denominators; unknown citation support is not a zero-citation response."""

from collections import Counter, defaultdict
from sqlalchemy import select, func
from app.ai.common import view
from .models import *
from . import core, extraction

CONTEXT = (
    "provider",
    "model",
    "country",
    "language",
    "location",
    "grounding",
    "cohort_type",
    "collection_method",
)


def selected(s, p, scope):
    originals = list(
        s.scalars(
            select(VisibilityObservation)
            .where(VisibilityObservation.project_id == p.id)
            .order_by(VisibilityObservation.imported_at.desc())
        )
    )
    superseded = {row.supersedes_id for row in originals if row.supersedes_id}
    included, excluded = [], []
    for row in originals:
        prompt = row.original["prompt_context"]
        reason = None
        for field in ("provider", "model", "collection_method"):
            if getattr(scope, field) is not None and getattr(row, field) != getattr(
                scope, field
            ):
                reason = "outside_" + field
        for field in ("category", "intent", "cohort_type"):
            if getattr(scope, field) not in (None, "all") and prompt.get(
                field
            ) != getattr(scope, field):
                reason = "outside_" + field
        if scope.start or scope.end:
            day = row.observed_at[:10] if row.observed_at else None
            if not day:
                reason = "unknown_collection_time"
            elif (
                scope.start
                and day < scope.start.isoformat()
                or scope.end
                and day > scope.end.isoformat()
            ):
                reason = "outside_time_window"
        if row.completeness == "invalid":
            reason = "invalid_observation"
        elif scope.require_complete and row.completeness != "complete":
            reason = "incomplete_observation"
        if row.id in superseded:
            reason = "superseded_by_auditable_correction"
        if reason:
            excluded.append({"observation_id": row.id, "reason": reason})
        else:
            included.append(row)
    return included, excluded


def bundles(s, observations):
    ids = [row.id for row in observations]
    if not ids:
        return []
    newest = (
        select(
            VisibilityExtraction.observation_id,
            func.max(VisibilityExtraction.revision).label("revision"),
        )
        .where(VisibilityExtraction.observation_id.in_(ids))
        .group_by(VisibilityExtraction.observation_id)
        .subquery()
    )
    revisions = list(
        s.scalars(
            select(VisibilityExtraction).join(
                newest,
                (VisibilityExtraction.observation_id == newest.c.observation_id)
                & (VisibilityExtraction.revision == newest.c.revision),
            )
        )
    )
    by_obs = {r.observation_id: r for r in revisions}
    extraction_ids = [r.id for r in revisions]
    mentions, citations = defaultdict(list), defaultdict(list)
    for row in s.scalars(
        select(VisibilityMention).where(
            VisibilityMention.extraction_id.in_(extraction_ids)
        )
    ):
        mentions[row.extraction_id].append(view(row))
    for row in s.scalars(
        select(VisibilityCitation).where(
            VisibilityCitation.extraction_id.in_(extraction_ids)
        )
    ):
        citations[row.extraction_id].append(view(row))
    return [
        {
            "observation": row,
            "extraction": by_obs.get(row.id),
            "mentions": mentions[by_obs[row.id].id] if row.id in by_obs else [],
            "citations": citations[by_obs[row.id].id] if row.id in by_obs else [],
        }
        for row in observations
    ]


def context(row):
    return {
        "provider": row.provider,
        "model": row.model,
        "collection_method": row.collection_method,
        **{
            k: row.original.get(k)
            for k in ("country", "language", "location", "grounding")
        },
        "cohort_type": row.original["prompt_context"]["cohort_type"],
    }


def grouped(rows):
    result = defaultdict(list)
    for bundle in rows:
        values = context(bundle["observation"])
        result[tuple(values.get(key) for key in CONTEXT)].append(bundle)
    return result


def confirmed_mentions(bundle, entity):
    return [
        m
        for m in bundle["mentions"]
        if m["entity_id"] == entity and m["status"] == "CONFIRMED_MATCH"
    ]


def confirmed_citations(bundle, entity=None):
    return [
        c
        for c in bundle["citations"]
        if c["attribution_status"] == "CONFIRMED_ATTRIBUTION"
        and c["ownership"] != "AMBIGUOUS"
        and (entity is None or c["entity_id"] == entity)
    ]


def citation_eligible(bundle):
    row, revision = bundle["observation"], bundle["extraction"]
    return (
        row.completeness == "complete"
        and revision is not None
        and revision.data["citation_complete"]
    )


def rate(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "percent": round(numerator / denominator * 100, 2) if denominator else None,
    }


def group_report(key, rows, registry, scope):
    brand = next(
        (
            e
            for e in registry
            if e["kind"] == "brand"
            and (not scope.brand_id or e["id"] == scope.brand_id)
        ),
        None,
    )
    competitors = [
        e
        for e in registry
        if e["kind"] == "competitor"
        and (not scope.competitor_id or e["id"] == scope.competitor_id)
    ]
    citation_rows = [b for b in rows if citation_eligible(b)]
    denominator = len(rows)
    comparison = []
    for entity in ([brand] if brand else []) + competitors:
        mentioned = [b for b in rows if confirmed_mentions(b, entity["id"])]
        cited = [b for b in citation_rows if confirmed_citations(b, entity["id"])]
        comparison.append(
            {
                "entity_id": entity["id"],
                "name": entity["name"],
                "kind": entity["kind"],
                "mention_rate": rate(len(mentioned), denominator),
                "citation_rate": rate(len(cited), len(citation_rows)),
                "citation_occurrences": sum(
                    len(confirmed_citations(b, entity["id"])) for b in rows
                ),
                "unique_cited_domains": sorted(
                    {
                        c["domain"]
                        for b in rows
                        for c in confirmed_citations(b, entity["id"])
                    }
                ),
                "overlapping_prompt_ids": sorted(
                    {
                        b["observation"].prompt_id
                        for b in mentioned
                        if brand and confirmed_mentions(b, brand["id"])
                    }
                ),
                "competitor_without_brand_observation_ids": [
                    b["observation"].id
                    for b in mentioned
                    if entity["kind"] == "competitor"
                    and brand
                    and not confirmed_mentions(b, brand["id"])
                ],
            }
        )
    domains = defaultdict(
        lambda: {"occurrences": 0, "urls": set(), "observations": set()}
    )
    for bundle in rows:
        for citation in confirmed_citations(bundle):
            domains[citation["domain"]]["occurrences"] += 1
            domains[citation["domain"]]["urls"].add(citation["normalized_url"])
            domains[citation["domain"]]["observations"].add(bundle["observation"].id)
    prompts = Counter(b["observation"].prompt_id for b in rows)
    warnings = (
        ["Tập mẫu nhỏ: luôn đọc tử số/mẫu số; không suy rộng thành thị phần AI."]
        if denominator < 20
        else []
    )
    if any(count > 1 for count in prompts.values()):
        warnings.append(
            "Có quan sát lặp cùng prompt; số lần chạy không phải số nguồn độc lập."
        )
    if any(value is None for value in key):
        warnings.append(
            "Metadata model/locale/thời gian chưa đầy đủ; giá trị Unknown không chứng minh context thực tế giống nhau."
        )
    if not citation_rows:
        warnings.append(
            "Không có quan sát đủ điều kiện tính citation rate; không hiển thị 0% thay cho Unknown."
        )
    brand_result = next((x for x in comparison if x["kind"] == "brand"), None)
    return {
        "cohort": dict(zip(CONTEXT, key)),
        "observation_count": denominator,
        "unique_prompt_count": len(prompts),
        "observation_ids": [b["observation"].id for b in rows],
        "collection_start": min(
            (
                b["observation"].observed_at
                for b in rows
                if b["observation"].observed_at
            ),
            default=None,
        ),
        "collection_end": max(
            (
                b["observation"].observed_at
                for b in rows
                if b["observation"].observed_at
            ),
            default=None,
        ),
        "brand_mention_rate": (
            brand_result["mention_rate"] if brand_result else rate(0, 0)
        ),
        "brand_citation_rate": (
            brand_result["citation_rate"] if brand_result else rate(0, 0)
        ),
        "entities": comparison,
        "citation_domain_distribution": [
            {
                "domain": domain,
                "citation_occurrences": data["occurrences"],
                "unique_cited_urls": len(data["urls"]),
                "observations_containing_domain": len(data["observations"]),
            }
            for domain, data in sorted(
                domains.items(), key=lambda x: -x[1]["occurrences"]
            )
        ],
        "citation_eligible_observations": len(citation_rows),
        "missing_citation_metadata": sum(
            b["observation"].citation_metadata != "complete" for b in rows
        ),
        "invalid_or_partial_citation_extraction": sum(
            b["observation"].citation_metadata == "complete"
            and not citation_eligible(b)
            for b in rows
        ),
        "unknown_citation_capability": sum(
            b["observation"].citation_capability == "unknown" for b in rows
        ),
        "coverage_notes": warnings,
    }


def overview(s, p, scope):
    registry = core.entities(s, p.id)
    if scope.brand_id:
        row = core.scoped(s, VisibilityEntity, scope.brand_id, p.id)
        if row.kind != "brand":
            core.fail("visibility_scope", "brand_id không phải brand chính.")
    if scope.competitor_id:
        row = core.scoped(s, VisibilityEntity, scope.competitor_id, p.id)
        if row.kind != "competitor":
            core.fail("visibility_scope", "competitor_id không phải đối thủ.")
    observations, exclusions = selected(s, p, scope)
    rows = bundles(s, observations)
    groups = [
        group_report(key, group, registry, scope)
        for key, group in grouped(rows).items()
    ]
    active = list(
        s.scalars(
            select(VisibilityPrompt).where(
                VisibilityPrompt.project_id == p.id, VisibilityPrompt.status == "active"
            )
        )
    )
    active_ids = {
        x.id
        for x in active
        if (not scope.category or x.category == scope.category)
        and (
            scope.cohort_type in (None, "all")
            or (
                "brand_specific"
                if x.cohort_type == "brand_specific"
                or any(
                    m["status"] != "REJECTED_MATCH"
                    for m in extraction.mentions(
                        x.text, [e for e in registry if e["kind"] == "brand"]
                    )
                )
                else x.cohort_type
            )
            == scope.cohort_type
        )
        and (not scope.intent or x.intent == scope.intent)
    }
    observed = {o.prompt_id for o in observations}
    return {
        "project_id": p.id,
        "scope": scope.model_dump(mode="json"),
        "eligible_observations": len(observations),
        "stored_observations": len(observations) + len(exclusions),
        "unique_prompts_observed": len(observed),
        "prompt_coverage": rate(len(active_ids & observed), len(active_ids)),
        "groups": groups,
        "cross_provider_comparable": False,
        "exclusion_counts": dict(Counter(x["reason"] for x in exclusions)),
        "excluded_observations": exclusions,
        "needs_review_mentions": sum(
            m["status"] in ("NEEDS_REVIEW", "POSSIBLE_MATCH")
            for b in rows
            for m in b["mentions"]
        ),
        "opportunities": s.scalar(
            select(func.count())
            .select_from(VisibilityOpportunity)
            .where(VisibilityOpportunity.project_id == p.id)
        ),
        "pending_review": s.scalar(
            select(func.count())
            .select_from(VisibilityOpportunity)
            .where(
                VisibilityOpportunity.project_id == p.id,
                VisibilityOpportunity.review_status.in_(
                    ["proposed", "under_review", "needs_more_evidence"]
                ),
            )
        ),
        "limitations": core.LIMITATIONS
        + (
            [
                "Nhiều cohort: báo cáo giữ riêng provider/model/locale/grounding/phương pháp; không có tỷ lệ tổng gộp."
            ]
            if len(groups) > 1
            else []
        ),
    }
