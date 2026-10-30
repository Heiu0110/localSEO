"""Explainable candidate rules. A finding is a stored observation, not a causal theory."""

import re
from collections import defaultdict
from sqlalchemy import select
from app.ai.common import uid, now, view
from .models import *
from . import core, metrics, evidence

RULES = {
    "GEO-MENTION-001": (
        "mention",
        "Đối thủ được nhắc, brand chưa có mention xác nhận",
        "mention + cùng quan sát hợp lệ",
        "Investigate",
    ),
    "GEO-CITE-001": (
        "citation",
        "Nguồn của đối thủ được trích dẫn trong quan sát",
        "provider citation + domain cấu hình",
        "Investigate",
    ),
    "GEO-CITE-002": (
        "citation",
        "Brand được nhắc nhưng chưa có owned citation",
        "mention xác nhận + citation metadata complete",
        "Investigate",
    ),
    "GEO-CITE-003": (
        "citation",
        "Nguồn brand được cite dù không có mention xác nhận",
        "owned citation xác nhận",
        "No Action",
    ),
    "GEO-TOPIC-001": (
        "topic",
        "Chủ đề ưu tiên chưa có mapping URL được duyệt",
        "prompt ưu tiên + mapping Research đã lưu",
        "Create Content Brief",
    ),
    "GEO-TECH-001": (
        "technical",
        "Vấn đề kỹ thuật đã ghi nhận trên URL liên quan",
        "URL liên kết rõ ràng + issue trong Technical Audit",
        "Review Technical SEO",
    ),
    "GEO-ENTITY-001": (
        "entity",
        "Thông tin doanh nghiệp khác nhau giữa các nguồn đã duyệt",
        "hai nguồn business identity user_verified",
        "Clarify Business Information",
    ),
    "GEO-SOURCE-001": (
        "source",
        "Nguồn ngoài được cite lặp trong cohort này",
        "ít nhất hai prompt khác nhau trong cohort so sánh được",
        "Investigate",
    ),
    "GEO-CONTENT-001": (
        "content",
        "Khoảng trống nội dung theo coverage review",
        "requirement + page content đã duyệt + đánh giá thiếu có lý do",
        "Improve Existing Content",
    ),
}
ACTIONS = {
    "GEO-MENTION-001": "Đọc prompt và câu trả lời gốc, kiểm tra alias/match mơ hồ; thu thêm quan sát so sánh được trước khi thay đổi trang.",
    "GEO-CITE-001": "Rà soát nguồn đối thủ đã cite; nhập nội dung nguồn hợp lệ nếu cần so sánh. Chưa có nội dung thì chỉ lập nhiệm vụ điều tra.",
    "GEO-CITE-002": "Kiểm tra tính đầy đủ citation và trang đích phù hợp; quan sát lại cùng context, không hứa hẹn bổ sung nội dung sẽ được cite.",
    "GEO-CITE-003": "Ghi nhận source visibility hữu ích. Không yêu cầu sửa trang chỉ vì brand không có mention trong câu trả lời này.",
    "GEO-TOPIC-001": "Đối chiếu các trang hiện có và Research mapping; duyệt URL phù hợp hoặc lập brief sau khi xác nhận khoảng trống.",
    "GEO-TECH-001": "Mở URL/Audit gốc, xác nhận lỗi và ý định index. Rà soát kỹ thuật trước, sau đó audit/quan sát lại; không suy ra nguyên nhân mất AI citation.",
    "GEO-ENTITY-001": "Nhờ chủ doanh nghiệp xác minh các giá trị và bối cảnh chi nhánh/tên cũ; chỉ đề xuất cập nhật sau khi xác nhận nguồn nào cần sửa.",
    "GEO-SOURCE-001": "Nghiên cứu mức liên quan/chất lượng của nguồn lặp trong tập mẫu; không sao chép nội dung hoặc coi số citation là traffic.",
    "GEO-CONTENT-001": "Rà soát requirement và toàn bộ nội dung trang đã nhập; xác nhận coverage review rồi lập cải thiện nội dung hữu ích, không chỉ thêm từ khóa.",
}


def catalog():
    return [
        {
            "id": id,
            "category": value[0],
            "description": value[1],
            "required_sources": value[2],
            "action": value[3],
            "confidence_criteria": "Fact theo nguồn; diễn giải và hành động chấm riêng. Đơn lẻ/lặp cùng prompt không chứng minh pattern phổ quát.",
            "limitations": "Không chứng minh nguyên nhân hoặc bảo đảm AI sẽ cite/nhắc brand.",
            "verification": "Đối chiếu nguồn gốc; sau thay đổi thu thập quan sát mới cùng cohort và ngày, giữ kết quả trước.",
        }
        for id, value in RULES.items()
    ]


def opportunity_view(s, row, full=True):
    analyses = (
        list(
            s.scalars(
                select(VisibilityAgentAnalysis)
                .where(VisibilityAgentAnalysis.opportunity_id == row.id)
                .order_by(VisibilityAgentAnalysis.created_at.desc())
                .limit(10)
            )
        )
        if full
        else []
    )
    return {
        **view(row),
        **row.data,
        "opportunity_id": row.id,
        "review_status": row.review_status,
        "analyses": [view(a) for a in analyses],
    }


def detect(s, db, p, scope):
    registry = core.entities(s, p.id)
    brand = next(
        (
            e
            for e in registry
            if e["kind"] == "brand"
            and (not scope.brand_id or scope.brand_id == e["id"])
        ),
        None,
    )
    if not brand:
        core.fail(
            "visibility_brand_required",
            "Cấu hình brand chính trước khi phát hiện cơ hội.",
            409,
        )
    # Validation and exclusions share exactly the same cohort contract as metrics.
    overview = metrics.overview(s, p, scope)
    observations, exclusions = metrics.selected(s, p, scope)
    bundles = metrics.bundles(s, observations)
    prompts = list(
        s.scalars(
            select(VisibilityPrompt).where(
                VisibilityPrompt.project_id == p.id, VisibilityPrompt.status == "active"
            )
        )
    )
    prompts = [
        x
        for x in prompts
        if (not scope.category or x.category == scope.category)
        and (not scope.intent or x.intent == scope.intent)
        and (scope.cohort_type in (None, "all") or x.cohort_type == scope.cohort_type)
    ]
    seo = evidence.seo_context(s, db, p, prompts)
    results, used_rules, truncated = [], set(), False

    def candidate(
        rule,
        eids,
        *,
        obs=None,
        topic="",
        urls=None,
        prompt_ids=None,
        facts=None,
        confidence="Limited",
        priority="Investigation",
        action=None,
        missing=None,
        explanation=None,
        counter=None,
    ):
        nonlocal truncated
        if len(results) >= 500:
            truncated = True
            return
        category, title, required, default_action = RULES[rule]
        obs = obs or []
        data = {
            "rule_id": rule,
            "rule_version": "geo-core-1.0",
            "title": title,
            "category": category,
            "affected_topic": topic,
            "affected_prompt_ids": sorted(
                set(prompt_ids or [x.prompt_id for x in obs])
            ),
            "affected_url_ids": sorted(set(urls or []))[:20],
            "observation_ids": [x.id for x in obs],
            "observation_count": len(obs),
            "evidence_ids": list(dict.fromkeys(eids)),
            "observed_facts": facts or [],
            "possible_explanations": explanation
            or ["Đây là quan sát/khả năng cần kiểm tra, chưa xác định nguyên nhân."],
            "counterevidence": counter or [],
            "missing_information": list(
                dict.fromkeys([*(missing or []), *seo["missing"]])
            ),
            "recommended_action": ACTIONS[rule],
            "action_type": action or default_action,
            "expected_benefit_hypothesis": "Giúp làm rõ dữ liệu hoặc tính hữu ích của trang; hiệu quả AI visibility cần kiểm chứng bằng quan sát mới.",
            "verification_plan": "Mở từng evidence, xác minh phạm vi/ngày. Nếu có chỉnh sửa, kiểm tra trực tiếp thay đổi rồi so quan sát mới cùng provider/model/locale/grounding/loại prompt; không coi approval là chứng minh nhân quả.",
            "evidence_confidence": confidence,
            "interpretation_confidence": (
                "Limited" if confidence in ("Verified", "Strong") else "Insufficient"
            ),
            "action_confidence": "Limited" if priority == "P1" else "Insufficient",
            "priority": priority,
            "priority_reason": (
                "P1: có vấn đề/nguồn cụ thể để rà soát."
                if priority == "P1"
                else "Cần điều tra: dữ liệu mẫu/quan sát chưa đủ để yêu cầu thay đổi cụ thể; không xếp P0 do brand vắng mặt."
            ),
            "scope": scope.model_dump(mode="json"),
            "cohort": metrics.context(obs[0]) if obs else None,
            "seo_evidence_ids": seo["evidence_ids"][:20],
            "limitations": core.LIMITATIONS,
            "claim_verification": "deterministic_facts_only",
            "recommendation_status": "needs_human_verification",
        }
        identity = core.digest(data)
        row = s.scalar(
            select(VisibilityOpportunity).where(
                VisibilityOpportunity.project_id == p.id,
                VisibilityOpportunity.identity == identity,
            )
        )
        if not row:
            row = VisibilityOpportunity(
                id=uid(),
                project_id=p.id,
                identity=identity,
                rule_id=rule,
                title=title,
                category=category,
                priority=priority,
                review_status="proposed",
                data=data,
                created_at=now(),
                updated_at=now(),
            )
            s.add(row)
            s.flush()
        results.append(row.id)
        used_rules.add(rule)

    for bundle in bundles:
        row = bundle["observation"]
        oid = evidence.observation(s, p, bundle, brand["id"])
        brand_mentions = metrics.confirmed_mentions(bundle, brand["id"])
        competitors = [
            m
            for m in bundle["mentions"]
            if m["entity_id"] != brand["id"]
            and m["status"] == "CONFIRMED_MATCH"
            and (not scope.competitor_id or m["entity_id"] == scope.competitor_id)
        ]
        topic = row.original["prompt_context"].get("topic", "")
        ambiguous_brand = any(
            m["entity_id"] == brand["id"]
            and m["status"] in ("NEEDS_REVIEW", "POSSIBLE_MATCH")
            for m in bundle["mentions"]
        )
        if competitors and not brand_mentions and not ambiguous_brand:
            eids = [oid]
            for mention in competitors[:4]:
                eids.append(
                    evidence.put(
                        s,
                        p.id,
                        "mention",
                        mention["id"],
                        {
                            **mention,
                            "entity_kind": "competitor",
                            "observation_id": row.id,
                        },
                        f"/ai-visibility?project={p.id}&observation={row.id}",
                    )
                )
            candidate(
                "GEO-MENTION-001",
                eids,
                obs=[row],
                topic=topic,
                missing=[
                    "Một quan sát không chứng minh pattern lặp hoặc brand kém hơn đối thủ.",
                    "Mention không đồng nghĩa recommendation.",
                ],
                facts=[
                    {
                        "predicate": "competitor_mentioned",
                        "evidence_ids": eids[1:],
                        "explanation": "Có mention đối thủ được xác nhận trong văn bản gốc.",
                    },
                    {
                        "predicate": "brand_not_observed",
                        "evidence_ids": [oid],
                        "explanation": "Chưa có mention brand được xác nhận; match mơ hồ không bị coi là vắng mặt chắc chắn.",
                    },
                ],
            )
        citations = metrics.confirmed_citations(bundle)
        owned = [c for c in citations if c["entity_id"] == brand["id"]]
        for citation in citations:
            if (
                citation["ownership"] == "COMPETITOR"
                and citation["source_type"]
                in ("provider_annotation", "grounding_metadata")
                and (
                    not scope.competitor_id
                    or citation["entity_id"] == scope.competitor_id
                )
            ):
                eid = evidence.put(
                    s,
                    p.id,
                    "citation",
                    citation["id"],
                    {**citation, "observation_id": row.id},
                    f"/ai-visibility?project={p.id}&observation={row.id}",
                )
                candidate(
                    "GEO-CITE-001",
                    [oid, eid],
                    obs=[row],
                    topic=topic,
                    urls=[citation["normalized_url"]],
                    confidence="Strong",
                    facts=[
                        {
                            "predicate": "competitor_citation",
                            "evidence_ids": [eid],
                            "explanation": "Nguồn báo citation đến domain đối thủ đã cấu hình; chưa kiểm chứng nội dung URL.",
                        }
                    ],
                    missing=[
                        "Chưa có nội dung nguồn để so sánh; không suy đoán vì sao AI chọn nguồn."
                    ],
                    counter=[
                        "Citation không chứng minh provider khuyên mua hàng từ đối thủ."
                    ],
                )
        if brand_mentions and not owned and metrics.citation_eligible(bundle):
            eid = evidence.put(
                s,
                p.id,
                "mention",
                brand_mentions[0]["id"],
                {**brand_mentions[0], "entity_kind": "brand", "observation_id": row.id},
                f"/ai-visibility?project={p.id}&observation={row.id}",
            )
            candidate(
                "GEO-CITE-002",
                [oid, eid],
                obs=[row],
                topic=topic,
                confidence="Strong",
                facts=[
                    {
                        "predicate": "brand_mentioned",
                        "evidence_ids": [eid],
                        "explanation": "Brand được nhắc; trong metadata citation đầy đủ của quan sát này chưa có owned citation.",
                    }
                ],
                missing=[
                    "Chưa có bằng chứng giải thích lựa chọn citation của provider."
                ],
            )
        if owned and not brand_mentions and not ambiguous_brand:
            eid = evidence.put(
                s,
                p.id,
                "citation",
                owned[0]["id"],
                {**owned[0], "observation_id": row.id},
                f"/ai-visibility?project={p.id}&observation={row.id}",
            )
            candidate(
                "GEO-CITE-003",
                [oid, eid],
                obs=[row],
                topic=topic,
                urls=[owned[0]["normalized_url"]],
                confidence=(
                    "Strong"
                    if owned[0]["source_type"]
                    in ("provider_annotation", "grounding_metadata")
                    else "Limited"
                ),
                action="No Action",
                facts=[
                    {
                        "predicate": "owned_citation",
                        "evidence_ids": [eid],
                        "explanation": "Nguồn thuộc brand được trích dẫn dù chưa có mention xác nhận.",
                    }
                ],
                counter=[
                    "Đây có thể là source visibility hữu ích; không tự coi là vấn đề cần sửa."
                ],
            )

    for prompt in prompts:
        urls = seo["url_map"].get(prompt.id, [])
        if prompt.priority >= 2 and not urls:
            eid = evidence.put(
                s,
                p.id,
                "prompt_mapping",
                prompt.id,
                {
                    "prompt_id": prompt.id,
                    "topic": prompt.data["topic"],
                    "text": prompt.text,
                    "references": prompt.data,
                    "approved_mapping_present": False,
                },
                "/ai-visibility?project=" + p.id,
            )
            candidate(
                "GEO-TOPIC-001",
                [eid],
                prompt_ids=[prompt.id],
                topic=prompt.data["topic"],
                action="Investigate",
                facts=[
                    {
                        "predicate": "mapping_missing",
                        "evidence_ids": [eid],
                        "explanation": "Chưa có target URL hoặc mapping được duyệt trong các tham chiếu Research/Tracking của prompt.",
                    }
                ],
                missing=[
                    "Cần đối chiếu nội dung website hiện có; chưa thể kết luận website không có trang phù hợp."
                ],
            )
        for issue in seo["technical"]:
            if (
                issue["url"] not in urls
                or issue["rule_id"]
                not in (
                    "INDEX-002",
                    "CRAWL-002",
                    "CRAWL-004",
                    "CAN-003",
                    "CAN-004",
                    "CAN-006",
                    "LINK-004",
                    "ARCH-003",
                )
                or issue["confidence"] not in ("confirmed", "strong_evidence")
            ):
                continue
            candidate(
                "GEO-TECH-001",
                [issue["evidence_id"]],
                prompt_ids=[prompt.id],
                topic=prompt.data["topic"],
                urls=[issue["url"]],
                confidence="Limited" if issue["stale"] else "Strong",
                priority="Investigation" if issue["stale"] else "P1",
                facts=[
                    {
                        "predicate": "technical_issue",
                        "evidence_ids": [issue["evidence_id"]],
                        "explanation": "Audit đã lưu ghi nhận issue này tại URL liên quan; chỉ phản ánh thời điểm/phạm vi audit.",
                    }
                ],
                missing=[
                    (
                        "Cần audit lại vì evidence cũ/chưa rõ ngày."
                        if issue["stale"]
                        else "Cần xác nhận ý định index và tình trạng hiện tại trước khi sửa."
                    ),
                    "Chưa chứng minh issue gây mất AI citation/mention.",
                ],
            )

    docs = list(
        s.scalars(
            select(VisibilityDocument).where(
                VisibilityDocument.project_id == p.id,
                VisibilityDocument.approved.is_(True),
            )
        )
    )
    identities = defaultdict(list)
    for doc in docs:
        if (
            doc.kind == "business_identity"
            and doc.data.get("verification") == "user_verified"
            and doc.data.get("entity_id")
        ):
            for field, value in doc.data.get("business_fields", {}).items():
                normalized = re.sub(r"\W+", "", value.casefold())
                identities[(doc.data["entity_id"], field)].append(
                    (doc, normalized, value)
                )
    for (entity_id, field), sources in identities.items():
        if len({value for _, value, _ in sources}) > 1:
            source_values = [
                {
                    "document_id": doc.id,
                    "url": doc.url,
                    "field": field,
                    "value": value,
                    "verification": "user_verified",
                }
                for doc, _, value in sources
            ]
            eid = evidence.put(
                s,
                p.id,
                "identity_conflict",
                entity_id + ":" + field,
                {"entity_id": entity_id, "field": field, "sources": source_values},
                "/ai-visibility?project=" + p.id,
            )
            candidate(
                "GEO-ENTITY-001",
                [eid],
                confidence="Strong",
                priority="P1",
                facts=[
                    {
                        "predicate": "identity_conflict",
                        "evidence_ids": [eid],
                        "explanation": "Có giá trị khác nhau trong các nguồn được người dùng xác minh và duyệt; chưa kết luận giá trị nào sai.",
                    }
                ],
                missing=[
                    "Khác biệt có thể do chi nhánh, tên cũ hoặc số điện thoại phụ; cần chủ doanh nghiệp xác minh."
                ],
                counter=[
                    "Approval của người dùng không phải chứng minh khách quan rằng thông tin doanh nghiệp sai."
                ],
            )

    for key, cohort in metrics.grouped(bundles).items():
        domains = defaultdict(list)
        for bundle in cohort:
            for cite in metrics.confirmed_citations(bundle):
                if cite["ownership"] == "THIRD_PARTY":
                    domains[cite["domain"]].append((bundle, cite))
        for domain, matches in domains.items():
            if len({bundle["observation"].prompt_id for bundle, _ in matches}) < 2:
                continue
            eids, selected = [], {}
            for bundle, citation in matches[:8]:
                selected[bundle["observation"].id] = bundle["observation"]
                eids.append(
                    evidence.put(
                        s,
                        p.id,
                        "citation",
                        citation["id"],
                        {**citation, "observation_id": bundle["observation"].id},
                        f"/ai-visibility?project={p.id}&observation={bundle['observation'].id}",
                    )
                )
            candidate(
                "GEO-SOURCE-001",
                eids,
                obs=list(selected.values()),
                topic=domain,
                confidence=(
                    "Strong"
                    if all(
                        c["source_type"]
                        in ("provider_annotation", "grounding_metadata")
                        for _, c in matches
                    )
                    else "Limited"
                ),
                urls=sorted({c["normalized_url"] for _, c in matches}),
                missing=[
                    "Chưa đọc nội dung nguồn; nghiên cứu tính liên quan/chất lượng, không sao chép nội dung.",
                    "Nhiều prompt không tự chứng minh các quan sát độc lập về mặt thống kê.",
                ],
            )

    latest_coverage = {}
    for assessment in s.scalars(
        select(VisibilityCoverage)
        .where(VisibilityCoverage.project_id == p.id)
        .order_by(VisibilityCoverage.created_at)
    ):
        latest_coverage[(assessment.requirement_id, assessment.page_id)] = assessment
    by_id = {doc.id: doc for doc in docs}
    for (rid, page_id), assessment in latest_coverage.items():
        requirement, page = by_id.get(rid), by_id.get(page_id)
        if assessment.decision != "missing" or not requirement or not page:
            continue
        eid = evidence.put(
            s,
            p.id,
            "coverage_review",
            assessment.id,
            {
                **view(assessment),
                "requirement": {
                    "id": rid,
                    "content": requirement.content[:2000],
                    "source_name": requirement.data["source_name"],
                },
                "page": {
                    "id": page_id,
                    "url": page.url,
                    "content_excerpt": page.content[:2000],
                    "content_sha256": core.digest(page.content),
                },
                "semantic_status": "human_reviewed_not_automatically_proven",
            },
            "/ai-visibility?project=" + p.id,
        )
        candidate(
            "GEO-CONTENT-001",
            [eid],
            prompt_ids=requirement.data.get("prompt_ids", []),
            topic=requirement.content[:160],
            urls=[page.url],
            confidence="Limited",
            priority="P2",
            facts=[
                {
                    "predicate": "coverage_review",
                    "evidence_ids": [eid],
                    "explanation": "Có requirement, nội dung trang thực nhập và review thiếu có lý do; không suy ra thiếu nội dung chỉ từ thiếu cụm từ.",
                }
            ],
            missing=[
                "Đánh giá ngữ nghĩa cần human verification; có thể có nội dung tương đương hoặc không cần bổ sung."
            ],
            counter=["Việc nội dung khác từ ngữ không tự chứng minh thiếu độ phủ."],
        )

    run = VisibilityRun(
        id=uid(),
        project_id=p.id,
        scope=scope.model_dump(mode="json"),
        data={
            "opportunity_ids": list(dict.fromkeys(results)),
            "included_observation_ids": [x.id for x in observations],
            "excluded_observations": exclusions,
            "rules_applied": sorted(used_rules),
            "abstentions": [
                {
                    "rule_id": rule,
                    "reason": "Không có evidence đáp ứng điều kiện trong scope này; không tạo finding thay thế.",
                }
                for rule in RULES
                if rule not in used_rules
            ],
            "summary": (
                "Có ứng viên để review; chưa xác định nguyên nhân AI chọn nguồn."
                if results
                else "Không đủ bằng chứng để đề xuất thay đổi. Không tạo lời khuyên chung để lấp danh sách."
            ),
            "truncated": truncated,
            "limit": 500,
            "seo_availability": seo,
            "metrics_snapshot": {
                "eligible_observations": overview["eligible_observations"],
                "cohort_count": len(overview["groups"]),
            },
        },
        created_at=now(),
    )
    s.add(run)
    s.flush()
    return view(run)
