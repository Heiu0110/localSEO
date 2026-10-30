"""Reference checks plus narrow claim predicates. Free semantics always need human review."""

import json
import re
from sqlalchemy import select
from app.ai.common import fail
from .models import *
from . import core


def reject_guarantees(value):
    text = json.dumps(value, ensure_ascii=False).casefold()
    guarantees = (
        r"(?:chắc chắn|cam kết|bảo đảm|đảm bảo).{0,80}(?:được.{0,20}trích dẫn|ai.{0,20}nhắc|ai ranking|đứng đầu)",
        r"guarantee.{0,80}(?:citation|ranking|ai visibility)",
        r"(?:noindex|faq schema).{0,100}(?:nguyên nhân duy nhất|sole cause|sole reason)",
    )
    for sentence in re.split(r"[.!?\n]", text):
        if re.search(
            r"không (?:thể |có |được )?(?:bảo đảm|đảm bảo|cam kết|chứng minh|kết luận)|not (?:a guarantee|proven)|cannot guarantee",
            sentence,
        ):
            continue
        if any(re.search(pattern, sentence) for pattern in guarantees):
            fail(
                "geo_unsupported_claim",
                "Đã chặn cam kết citation/ranking hoặc kết luận nhân quả không có căn cứ.",
                422,
            )


def check_evidence(s, p, eid, db):
    e = core.scoped(s, VisibilityEvidence, eid, p.id)
    value = e.data["value"]
    if e.source_type == "observation":
        row = core.scoped(s, VisibilityObservation, e.source_id, p.id)
        from .live_review import latest_review

        review = latest_review(s, row)
        if review and review.decision == "rejected":
            fail(
                "geo_stale_evidence",
                "Extraction đã bị người dùng từ chối; không dùng để phân tích GEO.",
                409,
            )
        latest = core.latest_extraction(s, row.id)
        if (
            not latest
            or latest.id != value.get("extraction_id")
            or s.scalar(
                select(VisibilityObservation.id).where(
                    VisibilityObservation.supersedes_id == row.id
                )
            )
        ):
            fail(
                "geo_stale_evidence",
                "Quan sát/nhận diện đã được sửa; phát hiện lại cơ hội trước khi phân tích.",
                409,
            )
        if latest.registry_hash != core.digest(core.entities(s, p.id)):
            fail(
                "geo_stale_evidence",
                "Registry đã đổi; tạo revision nhận diện mới rồi phát hiện lại cơ hội.",
                409,
            )
    elif e.source_type in ("mention", "citation"):
        model = VisibilityMention if e.source_type == "mention" else VisibilityCitation
        row = s.get(model, e.source_id)
        revision = s.get(VisibilityExtraction, row.extraction_id) if row else None
        if not revision:
            fail("geo_missing_evidence", "Bản ghi mention/citation không còn.", 409)
        obs = core.scoped(s, VisibilityObservation, revision.observation_id, p.id)
        from .live_review import latest_review

        review = latest_review(s, obs)
        if review and review.decision == "rejected":
            fail(
                "geo_stale_evidence",
                "Extraction đã bị từ chối; phát hiện lại GEO sau khi review nguồn.",
                409,
            )
        if core.latest_extraction(s, obs.id).id != revision.id or s.scalar(
            select(VisibilityObservation.id).where(
                VisibilityObservation.supersedes_id == obs.id
            )
        ):
            fail("geo_stale_evidence", "Evidence không còn là revision đang dùng.", 409)
        if revision.registry_hash != core.digest(core.entities(s, p.id)):
            fail(
                "geo_stale_evidence",
                "Domain/alias đã đổi; cần phân tích lại nhận diện.",
                409,
            )
        if e.source_type == "mention" and row.status != value["status"]:
            fail(
                "geo_stale_evidence",
                "Mention đã được review lại; phát hiện lại cơ hội.",
                409,
            )
    elif e.source_type == "coverage_review":
        row = core.scoped(s, VisibilityCoverage, e.source_id, p.id)
        latest = s.scalar(
            select(VisibilityCoverage)
            .where(
                VisibilityCoverage.requirement_id == row.requirement_id,
                VisibilityCoverage.page_id == row.page_id,
            )
            .order_by(VisibilityCoverage.created_at.desc())
            .limit(1)
        )
        if latest.id != row.id:
            fail("geo_stale_evidence", "Coverage review có phiên bản mới.", 409)
        for id in (row.requirement_id, row.page_id):
            if not core.scoped(s, VisibilityDocument, id, p.id).approved:
                fail("geo_stale_evidence", "Nguồn nội dung đã rút approval.", 409)
    elif e.source_type == "identity_conflict":
        for source in value["sources"]:
            if not core.scoped(
                s, VisibilityDocument, source["document_id"], p.id
            ).approved:
                fail(
                    "geo_stale_evidence",
                    "Nguồn thông tin doanh nghiệp đã rút approval.",
                    409,
                )
    elif e.source_type == "prompt_mapping":
        from .evidence import linked_urls

        row = core.scoped(s, VisibilityPrompt, e.source_id, p.id)
        if (
            row.data != value["references"]
            or bool(linked_urls(s, p, row)[0]) != value["approved_mapping_present"]
        ):
            fail("geo_stale_evidence", "Mapping đã đổi; phát hiện lại cơ hội.", 409)
    elif e.source_type in ("research_keyword", "research_cluster", "tracked_keyword"):
        from app.research.models import (
            ResearchKeyword,
            ResearchCluster,
            ResearchProject,
        )
        from app.keywords.models import TrackedKeyword, KeywordSet

        model = {
            "research_keyword": ResearchKeyword,
            "research_cluster": ResearchCluster,
            "tracked_keyword": TrackedKeyword,
        }[e.source_type]
        row = s.get(model, e.source_id)
        source = (
            (
                s.get(KeywordSet, row.keyword_set_id)
                if e.source_type == "tracked_keyword"
                else s.get(ResearchProject, row.project_id)
            )
            if row
            else None
        )
        site = (
            source.site_id
            if e.source_type == "tracked_keyword" and source
            else source.local_project_id if source else None
        )
        if site != p.local_project_id:
            fail(
                "visibility_scope",
                "Nguồn Research/Tracking không còn thuộc website đã khóa.",
                403,
            )
        if (
            row.target_url != value.get("target_url")
            or e.source_type != "tracked_keyword"
            and row.mapping_status != value.get("mapping_status")
        ):
            fail(
                "geo_stale_evidence",
                "Mapping Research/Tracking đã đổi; phát hiện lại cơ hội.",
                409,
            )
    elif e.source_type in ("technical_issue", "audit_url", "internal_link"):
        from app.technical.models import AuditIssue, AuditURL, AuditLink, AuditRun
        from app.ai.context import project as site_project, audit_projects

        model = {
            "technical_issue": AuditIssue,
            "audit_url": AuditURL,
            "internal_link": AuditLink,
        }[e.source_type]
        row = s.get(
            model, int(e.source_id) if e.source_type == "internal_link" else e.source_id
        )
        allowed = {
            a.id for a in audit_projects(db, site_project(db, p.local_project_id))
        }
        if not row:
            fail(
                "geo_missing_evidence", "Bản ghi Technical SEO không còn tồn tại.", 409
            )
        run = s.get(AuditRun, row.audit_id)
        if not run or run.project_id not in allowed:
            fail(
                "visibility_scope",
                "Technical evidence không thuộc website đã khóa.",
                403,
            )
    return e


def supports(claim, evidence):
    rows = [evidence[id] for id in claim["evidence_ids"]]
    for e in rows:
        kind, value = e.source_type, e.data["value"]
        predicate = claim["predicate"]
        if (
            predicate in ("brand_mentioned", "competitor_mentioned")
            and kind == "mention"
            and value.get("status") == "CONFIRMED_MATCH"
            and value.get("entity_kind")
            == ("brand" if predicate == "brand_mentioned" else "competitor")
        ):
            return True
        if (
            predicate == "brand_not_observed"
            and kind == "observation"
            and value.get("complete")
            and value.get("brand_mention_confirmed") is False
            and not value.get("ambiguous_brand_match")
        ):
            return True
        if (
            predicate in ("owned_citation", "competitor_citation")
            and kind == "citation"
            and value.get("attribution_status") == "CONFIRMED_ATTRIBUTION"
            and value.get("ownership")
            == ("OWNED_BRAND" if predicate == "owned_citation" else "COMPETITOR")
        ):
            return True
        if (
            predicate == "technical_issue"
            and kind == "technical_issue"
            and value.get("confidence") in ("confirmed", "strong_evidence")
        ):
            return True
        if (
            predicate == "mapping_missing"
            and kind == "prompt_mapping"
            and value.get("approved_mapping_present") is False
        ):
            return True
        if (
            predicate == "identity_conflict"
            and kind == "identity_conflict"
            and len({x["value"] for x in value["sources"]}) > 1
        ):
            return True
        if (
            predicate == "coverage_review"
            and kind == "coverage_review"
            and value.get("decision") == "missing"
        ):
            return True
    return False


def verify(s, p, opportunity, result, available_ids, db):
    from .schemas import GEOOpportunityAnalysis

    result = GEOOpportunityAnalysis.model_validate(result).model_dump(mode="json")
    if result["project_id"] != p.id:
        fail("geo_scope", "AI trả project khác ngữ cảnh đã khóa.", 403)
    reject_guarantees(result)
    evidence = {eid: check_evidence(s, p, eid, db) for eid in available_ids}
    accepted_claims, human_claims = [], []
    items = [
        *result["findings"],
        *[claim for row in result["opportunities"] for claim in row["observed_facts"]],
    ]
    for claim in items:
        if not set(claim["evidence_ids"]) <= set(evidence):
            fail(
                "geo_invented_evidence",
                "AI dẫn evidence chưa được cấp cho lượt phân tích.",
                422,
            )
        if claim["predicate"] == "hypothesis" or not supports(claim, evidence):
            human_claims.append({**claim, "status": "Needs Human Verification"})
        else:
            accepted_claims.append(
                {
                    **claim,
                    "status": "Predicate Verified — explanation still requires human review",
                }
            )
    prerequisites = {
        "Improve Existing Content": {"coverage_review"},
        "Expand Topic Coverage": {"coverage_review"},
        "Differentiate Content": {"coverage_review"},
        "Review Technical SEO": {"technical_issue"},
        "Clarify Business Information": {"identity_conflict"},
        "Improve Internal Linking": {"internal_link"},
        "Improve Page Structure": {"audit_url"},
        "Create Content Brief": {"prompt_mapping", "coverage_review"},
    }
    downgrades = []
    for row in result["opportunities"]:
        if row["opportunity_id"] != opportunity.id or not set(
            row["evidence_ids"]
        ) <= set(evidence):
            fail("geo_scope", "AI trả opportunity/evidence ngoài scope đã khóa.", 403)
        if not set(row["affected_prompt_ids"]) <= set(
            opportunity.data["affected_prompt_ids"]
        ) or not set(row["affected_url_ids"]) <= set(
            opportunity.data["affected_url_ids"]
        ):
            fail(
                "geo_unsourced_target",
                "AI đề xuất prompt/URL chưa có trong evidence của cơ hội.",
                422,
            )
        kinds = {evidence[eid].source_type for eid in row["evidence_ids"]}
        required = prerequisites.get(row["action_type"])
        if required and not kinds & required or row["priority"] == "P0":
            downgrades.append(
                "Thiếu bằng chứng cho hành động hoặc mức ưu tiên; hạ thành điều tra."
            )
            row.update(
                action_type="Investigate",
                priority="Investigation",
                action_confidence="Insufficient",
                recommended_action="Điều tra thêm bằng chứng phù hợp trước khi chỉ định thay đổi. Đối chiếu nguồn gốc và bổ sung dữ liệu còn thiếu; chưa thực hiện đề xuất ban đầu.",
            )
            row["missing_information"] = [
                *row["missing_information"],
                "Chưa đủ bằng chứng phù hợp để chỉ định thay đổi; cần human verification.",
            ][:10]
        levels = ["Insufficient", "Ambiguous", "Limited", "Strong", "Verified"]
        if levels.index(row["evidence_confidence"]) > levels.index(
            opportunity.data["evidence_confidence"]
        ):
            row["evidence_confidence"] = opportunity.data["evidence_confidence"]
        row["review_status"] = "needs_human_verification"
        row["category"] = opportunity.category
        if row["interpretation_confidence"] in ("Verified", "Strong"):
            row["interpretation_confidence"] = "Limited"
        if row["action_confidence"] in ("Verified", "Strong"):
            row["action_confidence"] = "Limited"
    return {
        "analysis": result,
        "verified_predicates": accepted_claims,
        "claims_needing_human_verification": human_claims,
        "downgrades": downgrades,
        "status": (
            "Needs Human Verification"
            if result["opportunities"] or items
            else "Insufficient evidence — abstained"
        ),
        "semantic_assertions_automatically_confirmed": False,
        "approval_executes_changes": False,
    }
