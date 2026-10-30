"""Actually implemented read-only tools; website scope is injected by ToolRegistry."""

from pydantic import Field
from sqlalchemy import select
from app.ai.schemas import Input
from app.ai.common import view, fail
from .models import *
from .schemas import Cohort
from . import core, metrics, agent_integration


class VisibilityArgs(Input):
    visibility_id: str | None = Field(default=None, max_length=100)
    provider: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=160)
    limit: int = Field(default=4, ge=1, le=5)


class ObservationArgs(VisibilityArgs):
    observation_id: str = Field(min_length=1, max_length=100)


class OpportunityArgs(VisibilityArgs):
    opportunity_id: str = Field(min_length=1, max_length=100)


SPECS = {
    "get_ai_visibility_overview": (
        VisibilityArgs,
        "Tử số/mẫu số theo từng cohort quan sát đã lưu, không phải thị phần AI.",
    ),
    "get_visibility_prompt_cohort": (
        VisibilityArgs,
        "Prompt/country/language/source đã lưu; branded khác neutral.",
    ),
    "get_visibility_observation": (
        ObservationArgs,
        "Đọc excerpt quan sát, mention/citation và provenance; không thu thập mới.",
    ),
    "get_brand_mentions": (
        VisibilityArgs,
        "Mention xác nhận và match mơ hồ tách riêng, không suy ra recommendation.",
    ),
    "get_brand_citations": (
        VisibilityArgs,
        "Citation tường minh/ownership đã cấu hình, không coi URL thường là citation.",
    ),
    "get_competitor_visibility": (
        VisibilityArgs,
        "Đối thủ trong từng cohort đã lưu, không gộp provider/model khác context.",
    ),
    "get_cited_source_summary": (
        VisibilityArgs,
        "Nguồn cite theo occurrences/unique URL/observations; không bịa nội dung nguồn.",
    ),
    "get_geo_opportunities": (
        VisibilityArgs,
        "Ứng viên GEO đã phát hiện kèm priority/review/evidence; không phát hiện hay ghi mới.",
    ),
    "get_geo_opportunity_evidence": (
        OpportunityArgs,
        "GEOAnalysisContext có provenance và bounded evidence, kiểm tra scope/revision trước khi đọc.",
    ),
}


def execute(registry, name, args, site):
    with registry.db.session() as s:
        q = select(VisibilityProject).where(
            VisibilityProject.local_project_id == site["id"]
        )
        if args.visibility_id:
            q = q.where(VisibilityProject.id == args.visibility_id)
        p = s.scalar(q.order_by(VisibilityProject.updated_at.desc()).limit(1))
        if args.visibility_id and not p:
            fail(
                "visibility_scope",
                "Visibility project không thuộc website của hội thoại.",
                403,
            )
        record, reference = None, "/ai-visibility"
        if not p:
            data = {
                "available": False,
                "reason": "Chưa có Visibility project/quan sát cho website; không bịa AI visibility.",
            }
        else:
            record, reference = p.id, "/ai-visibility?project=" + p.id
            scope = Cohort(provider=args.provider, model=args.model)
            if name == "get_geo_opportunity_evidence":
                row = core.scoped(s, VisibilityOpportunity, args.opportunity_id, p.id)
                data = agent_integration.context_packet(s, p, row, registry.db)
                record = row.id
            elif name == "get_geo_opportunities":
                rows = list(
                    s.scalars(
                        select(VisibilityOpportunity)
                        .where(VisibilityOpportunity.project_id == p.id)
                        .order_by(VisibilityOpportunity.updated_at.desc())
                        .limit(args.limit)
                    )
                )
                data = {
                    "rows": [
                        {
                            "id": row.id,
                            "title": row.title,
                            "rule_id": row.rule_id,
                            "priority": row.priority,
                            "review_status": row.review_status,
                            "evidence_ids": row.data["evidence_ids"],
                            "action": row.data["recommended_action"],
                            "priority_reason": row.data["priority_reason"],
                        }
                        for row in rows
                    ]
                }
            elif name == "get_visibility_prompt_cohort":
                rows = list(
                    s.scalars(
                        select(VisibilityPrompt)
                        .where(VisibilityPrompt.project_id == p.id)
                        .limit(args.limit)
                    )
                )
                data = {
                    "rows": [
                        {
                            "id": row.id,
                            "text": row.text,
                            "category": row.category,
                            "intent": row.intent,
                            "cohort_type": row.cohort_type,
                            "source": row.data["source"],
                        }
                        for row in rows
                    ]
                }
            elif name == "get_visibility_observation":
                row = core.scoped(s, VisibilityObservation, args.observation_id, p.id)
                data = core.observation_view(s, row, False)
                data.pop("limitations", None)
                data["mentions"] = data["mentions"][: args.limit]
                data["citations"] = data["citations"][: args.limit]
                record = row.id
            else:
                report = metrics.overview(s, p, scope)
                if name in (
                    "get_ai_visibility_overview",
                    "get_competitor_visibility",
                    "get_cited_source_summary",
                ):
                    data = {
                        "eligible_observations": report["eligible_observations"],
                        "unique_prompts_observed": report["unique_prompts_observed"],
                        "groups": [],
                    }
                    for group in report["groups"][: args.limit]:
                        selected = {
                            k: group[k]
                            for k in (
                                "cohort",
                                "observation_count",
                                "unique_prompt_count",
                                "brand_mention_rate",
                                "brand_citation_rate",
                            )
                        }
                        if name == "get_competitor_visibility":
                            selected["entities"] = group["entities"][: args.limit]
                        if name == "get_cited_source_summary":
                            selected["domains"] = group["citation_domain_distribution"][
                                : args.limit
                            ]
                            selected["content_analysis_available"] = False
                        data["groups"].append(selected)
                else:
                    observations, _ = metrics.selected(s, p, scope)
                    selected = metrics.bundles(s, observations[:20])
                    kind = "mentions" if name == "get_brand_mentions" else "citations"
                    brand_ids = {
                        e["id"] for e in core.entities(s, p.id) if e["kind"] == "brand"
                    }
                    data = {
                        "rows": [
                            {**row, "observation_id": bundle["observation"].id}
                            for bundle in selected
                            for row in bundle[kind]
                            if row["entity_id"] in brand_ids
                        ][: args.limit],
                        "scope": "bounded_stored_brand_observations",
                    }
        return registry.evidence(
            site,
            "AI Visibility",
            data,
            record=record,
            scope="stored_visibility_project_and_cohort",
            reference=reference,
            completeness="bounded_stored_evidence",
            limitations=core.LIMITATIONS,
        )
