"""Attach bounded GEO packets to the existing AIManager; no second chat/provider stack."""

import json
from sqlalchemy import select
from app.ai.common import fail, uid, now, view
from app.ai.schemas import Analysis
from .schemas import GEOAnalysisContext, GEOOpportunityAnalysis, GEOOpportunityOutput
from .models import *
from . import core, verification


class GEOAgentAnalysis(Analysis):
    geo_analysis: GEOOpportunityAnalysis


def require_scope(db, local_site_id, scope):
    with db.session() as s:
        p = core.project(s, scope.visibility_project_id)
        if p.local_project_id != local_site_id:
            fail(
                "visibility_scope",
                "GEO project không thuộc website của hội thoại.",
                403,
            )
        row = core.scoped(s, VisibilityOpportunity, scope.opportunity_id, p.id)
        for eid in row.data["evidence_ids"]:
            verification.check_evidence(s, p, eid, db)
        return p, row


def context_packet(s, p, row, db):
    ids = list(
        dict.fromkeys(row.data["evidence_ids"][:8] + row.data["seo_evidence_ids"][:2])
    )
    snippets = []
    for id in ids:
        item = verification.check_evidence(s, p, id, db)
        value = item.data["value"]
        keep = {
            k: value[k]
            for k in (
                "url",
                "normalized_url",
                "entity_id",
                "entity_kind",
                "ownership",
                "attribution_status",
                "source_type",
                "status",
                "matched_text",
                "prompt_id",
                "observed_at",
                "complete",
                "citation_eligible",
                "brand_mention_confirmed",
                "ambiguous_brand_match",
                "rule_id",
                "title",
                "stale",
                "age_days",
                "decision",
                "field",
                "approved_mapping_present",
            )
            if k in value
        }
        if "sources" in value:
            keep["sources"] = value["sources"][:3]
        if "requirement" in value:
            keep["requirement"] = {
                **value["requirement"],
                "content": value["requirement"]["content"][:400],
            }
            keep["page"] = {
                "id": value["page"]["id"],
                "url": value["page"]["url"],
                "untrusted_content_excerpt": value["page"]["content_excerpt"][:400],
            }
        if "reason" in value:
            keep["reason"] = value["reason"][:400]
        snippets.append(
            {
                "evidence_id": id,
                "source_type": item.source_type,
                "source_record_id": item.source_id,
                "value": keep,
                "source_reference": item.data["source_reference"],
            }
        )
    fields = (
        "title",
        "rule_id",
        "category",
        "affected_topic",
        "affected_prompt_ids",
        "affected_url_ids",
        "observed_facts",
        "recommended_action",
        "action_type",
        "priority",
        "priority_reason",
        "evidence_confidence",
        "interpretation_confidence",
        "action_confidence",
        "counterevidence",
    )
    packet = GEOAnalysisContext(
        local_project_id=p.local_project_id,
        visibility_project_id=p.id,
        opportunity_id=row.id,
        objective=p.research_goal
        or "Điều tra cơ hội GEO bằng evidence, cho phép abstain; không cam kết citation.",
        cohort=row.data.get("cohort") or {},
        candidate={k: row.data[k] for k in fields},
        evidence=snippets,
        available_evidence_ids=ids,
        limitations=[
            *core.LIMITATIONS,
            *row.data["missing_information"][:4],
            "Excerpt không thay thế toàn bộ nội dung; giải thích ngữ nghĩa vẫn cần human verification.",
        ],
    )
    return packet.model_dump(mode="json")


def local_analysis(packet, envelope_id):
    """The existing offline reporting provider remains useful without a cloud model."""
    c = packet["candidate"]
    opportunity = {
        key: c[key]
        for key in (
            "title",
            "affected_topic",
            "affected_prompt_ids",
            "affected_url_ids",
            "observed_facts",
            "recommended_action",
            "action_type",
            "evidence_confidence",
            "interpretation_confidence",
            "action_confidence",
            "priority",
        )
    }
    opportunity.update(
        opportunity_id=packet["opportunity_id"],
        category=c["category"],
        evidence_ids=[
            id
            for id in packet["available_evidence_ids"]
            if id
            in {eid for fact in c["observed_facts"] for eid in fact["evidence_ids"]}
        ],
        possible_explanations=[
            "Chưa có phân tích ngữ nghĩa bằng mô hình; giữ hypothesis ở mức cần xác minh."
        ],
        counterevidence=c["counterevidence"][:4],
        missing_information=packet["limitations"][:8],
        expected_benefit_hypothesis="Cải thiện hiểu biết về evidence; không bảo đảm AI citation.",
        verification_plan="Đọc evidence gốc, kiểm tra điều kiện rule và ngày. Sau thay đổi, quan sát lại cùng cohort và lưu cả kết quả trước/sau.",
        review_status="needs_human_verification",
    )
    if not opportunity["evidence_ids"]:
        opportunity["evidence_ids"] = packet["available_evidence_ids"][:1]
    geo = GEOOpportunityAnalysis(
        project_id=packet["visibility_project_id"],
        observation_scope=json.dumps(packet["cohort"], ensure_ascii=False),
        summary="Báo cáo ngoại tuyến từ rule và evidence đã lưu; các diễn giải/hành động cần người dùng xác minh.",
        findings=c["observed_facts"],
        opportunities=[GEOOpportunityOutput.model_validate(opportunity)],
        limitations=packet["limitations"][:12],
        next_investigation="Rà soát evidence và quyết định cần bổ sung nguồn nào trước khi thay đổi website.",
    )
    return GEOAgentAnalysis(
        summary=geo.summary,
        findings=[
            {
                "title": c["title"],
                "interpretation": c["priority_reason"],
                "evidence_ids": [envelope_id],
                "confidence": "low",
                "kind": "hypothesis",
            }
        ],
        recommendations=[
            {
                "title": c["title"],
                "proposed_action": c["recommended_action"],
                "priority": "low",
                "confidence": "low",
                "evidence_ids": [envelope_id],
            }
        ],
        limitations=geo.limitations,
        next_step=geo.next_investigation,
        geo_analysis=geo,
    ).model_dump(mode="json")


def finalize(db, local_site_id, scope, message_id, analysis, available_ids):
    verification.reject_guarantees(analysis)
    with db.session.begin() as s:
        p = core.project(s, scope["visibility_project_id"])
        if p.local_project_id != local_site_id:
            fail("visibility_scope", "Website đã đổi so với scope phân tích.", 403)
        row = core.scoped(s, VisibilityOpportunity, scope["opportunity_id"], p.id)
        if not analysis.get("geo_analysis"):
            fail("geo_missing_output", "AI chưa trả GEO output có cấu trúc.", 422)
        verified = verification.verify(
            s, p, row, analysis["geo_analysis"], available_ids, db
        )
        saved = VisibilityAgentAnalysis(
            id=uid(),
            project_id=p.id,
            opportunity_id=row.id,
            message_id=message_id,
            data=verified,
            created_at=now(),
        )
        s.add(saved)
        return verified
