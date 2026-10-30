"""Scoped local writes and immutable observation ingestion."""

import hashlib
import json
from datetime import timezone
from urllib.parse import urlsplit
from sqlalchemy import select, func
from app.ai.common import fail, uid, now, view
from app.ai.context import project as local_project
from app.research.models import ResearchProject, ResearchKeyword, ResearchCluster
from app.keywords.models import KeywordSet, TrackedKeyword
from .models import *
from . import extraction
from .schemas import ObservationInput

LIMITS = {
    "projects": 100,
    "prompts": 2000,
    "observations": 2000,
    "import_rows": 100,
    "file_bytes": 102400,
}
LIMITATIONS = [
    "Chỉ đo tập quan sát đã lưu, không phải thị phần, traffic, ranking hoặc trải nghiệm của mọi người dùng AI.",
    "Mention, citation, URL xuất hiện trong văn bản và lời khuyên mua hàng là các khái niệm riêng.",
    "Citation được nguồn báo cáo không chứng minh URL đang hoạt động hoặc nội dung hỗ trợ một khẳng định.",
    "Không có provider live, tự crawl nguồn trích dẫn, lịch chạy hàng loạt hoặc thay đổi website trong v0.8 Core.",
]


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


def scoped(s, model, id, project_id):
    result = s.get(model, id)
    if not result:
        fail("visibility_not_found", "Không tìm thấy dữ liệu AI Visibility.", 404)
    if result.project_id != project_id:
        fail("visibility_scope", "Dữ liệu thuộc Visibility project khác.", 403)
    return result


def project(s, id):
    p = s.get(VisibilityProject, id)
    if not p:
        fail("visibility_not_found", "Không tìm thấy Visibility project.", 404)
    return p


def new_project(s, db, data):
    local_project(db, data.local_project_id)
    if (
        not data.name.strip()
        or s.scalar(select(func.count()).select_from(VisibilityProject))
        >= LIMITS["projects"]
    ):
        fail("visibility_limit", "Tên dự án trống hoặc đã đạt giới hạn dự án.")
    p = VisibilityProject(
        id=uid(),
        **data.model_dump(),
        status="active",
        created_at=now(),
        updated_at=now()
    )
    s.add(p)
    s.flush()
    return p


def entities(s, pid):
    return [
        view(row)
        for row in s.scalars(
            select(VisibilityEntity)
            .where(VisibilityEntity.project_id == pid)
            .order_by(VisibilityEntity.created_at)
        )
    ]


def save_entity(s, p, data, id=None):
    values = data.model_dump()
    if not values["name"].strip():
        fail("visibility_entity", "Tên thực thể không được trống.")
    if (
        not id
        and values["kind"] == "brand"
        and s.scalar(
            select(VisibilityEntity.id).where(
                VisibilityEntity.project_id == p.id, VisibilityEntity.kind == "brand"
            )
        )
    ):
        fail(
            "visibility_entity",
            "Một project có một brand chính; tạo project riêng để đo brand khác.",
            409,
        )
    config = {k: v for k, v in values.items() if k not in ("name", "kind")}
    try:
        for domain in config["domains"]:
            domain["domain"] = extraction.domain_name(domain["domain"])
        config["social_profiles"] = [
            extraction.normalize_url(value) for value in config["social_profiles"]
        ]
        if any(
            urlsplit(value).path in ("", "/") for value in config["social_profiles"]
        ):
            raise ValueError("Social profile needs an account path")
    except ValueError:
        fail(
            "visibility_entity",
            "Domain/profile không hợp lệ; không dùng wildcard hoặc URL có credentials.",
        )
    if len(json.dumps(config)) > 20000 or any(
        len(term) > 160
        for alias in config["aliases"]
        for term in [*alias["context_terms"], *alias["negative_terms"]]
    ):
        fail("visibility_entity", "Cấu hình entity quá dài.")
    if id:
        row = scoped(s, VisibilityEntity, id, p.id)
        if row.kind != values["kind"]:
            fail("visibility_entity", "Không đổi kind của entity đã có lịch sử.")
        s.add(
            VisibilityReview(
                id=uid(),
                project_id=p.id,
                entity_type="entity_config",
                entity_id=id,
                decision="revised",
                data={"before": view(row), "after": values},
                created_at=now(),
            )
        )
        row.name, row.config, row.updated_at = values["name"], config, now()
    else:
        row = VisibilityEntity(
            id=uid(),
            project_id=p.id,
            kind=values["kind"],
            name=values["name"],
            config=config,
            created_at=now(),
            updated_at=now(),
        )
        s.add(row)
    s.flush()
    return row


def validate_prompt_refs(s, p, values):
    cluster_id = values.get("research_cluster_id")
    if cluster_id:
        cluster = s.get(ResearchCluster, cluster_id)
        rp = s.get(ResearchProject, cluster.project_id) if cluster else None
        if not rp or rp.local_project_id != p.local_project_id:
            fail("visibility_scope", "Research cluster không thuộc website này.", 403)
    for keyword_id in values.get("research_keyword_ids", []):
        keyword = s.get(ResearchKeyword, keyword_id)
        rp = s.get(ResearchProject, keyword.project_id) if keyword else None
        if not rp or rp.local_project_id != p.local_project_id:
            fail("visibility_scope", "Research keyword không thuộc website này.", 403)
    if values.get("tracking_keyword_id"):
        keyword = s.get(TrackedKeyword, values["tracking_keyword_id"])
        ks = s.get(KeywordSet, keyword.keyword_set_id) if keyword else None
        if not ks or ks.site_id != p.local_project_id:
            fail("visibility_scope", "Tracking keyword không thuộc website này.", 403)


def save_prompt(s, p, data, id=None):
    values = data.model_dump(mode="json")
    validate_prompt_refs(s, p, values)
    if not values["text"].strip():
        fail("visibility_prompt", "Prompt không được trống.")
    if values["target_url"]:
        try:
            values["target_url"] = extraction.normalize_url(values["target_url"])
        except ValueError:
            fail("visibility_prompt", "Target URL không hợp lệ.")
    identity = digest(
        {
            k: values[k]
            for k in (
                "text",
                "language",
                "country",
                "location",
                "category",
                "cohort_type",
            )
        }
    )
    existing = s.scalar(
        select(VisibilityPrompt).where(
            VisibilityPrompt.project_id == p.id, VisibilityPrompt.identity == identity
        )
    )
    if existing and not id:
        return existing, False
    fields = {
        k: values[k]
        for k in ("text", "category", "intent", "cohort_type", "priority", "status")
    }
    remaining = {k: v for k, v in values.items() if k not in fields}
    if id:
        row = scoped(s, VisibilityPrompt, id, p.id)
        s.add(
            VisibilityReview(
                id=uid(),
                project_id=p.id,
                entity_type="prompt",
                entity_id=id,
                decision="revised",
                data={"before": view(row), "after": values},
                created_at=now(),
            )
        )
        for k, v in fields.items():
            setattr(row, k, v)
        row.identity, row.data, row.updated_at = identity, remaining, now()
    else:
        if (
            s.scalar(
                select(func.count())
                .select_from(VisibilityPrompt)
                .where(VisibilityPrompt.project_id == p.id)
            )
            >= LIMITS["prompts"]
        ):
            fail("visibility_limit", "Đã đạt giới hạn prompt cho project.")
        row = VisibilityPrompt(
            id=uid(),
            project_id=p.id,
            identity=identity,
            **fields,
            data=remaining,
            created_at=now(),
            updated_at=now()
        )
        s.add(row)
    s.flush()
    return row, True


def prompt_view(row):
    return {**view(row), **row.data}


def latest_extraction(s, oid):
    return s.scalar(
        select(VisibilityExtraction)
        .where(VisibilityExtraction.observation_id == oid)
        .order_by(VisibilityExtraction.revision.desc())
        .limit(1)
    )


def extract(s, observation):
    registry = entities(s, observation.project_id)
    previous = latest_extraction(s, observation.id)
    revision = VisibilityExtraction(
        id=uid(),
        observation_id=observation.id,
        revision=previous.revision + 1 if previous else 1,
        registry_hash=digest(registry),
        config_snapshot=registry,
        data={},
        created_at=now(),
    )
    s.add(revision)
    s.flush()
    for match in extraction.mentions(observation.response_text, registry):
        s.add(
            VisibilityMention(
                id=uid(),
                extraction_id=revision.id,
                detected_status=match["status"],
                **match
            )
        )
    native, warnings = extraction.native_citations(
        observation.original.get("raw_annotations", {})
    )
    citations, problems = extraction.citation_rows(
        observation.response_text,
        [*observation.original.get("citations", []), *native],
        registry,
    )
    for citation in citations:
        s.add(VisibilityCitation(id=uid(), extraction_id=revision.id, **citation))
    revision.data = {
        "warnings": [*warnings, *problems],
        "url_mentions": extraction.url_mentions(observation.response_text),
        "citation_complete": observation.citation_capability == "capable"
        and observation.citation_metadata == "complete"
        and not warnings
        and not problems,
        "rule_version": "visibility-extraction-1.0",
    }
    s.flush()
    return revision


def ingest(s, p, data, *, supersedes=None, reason=None, import_job=None):
    prompt = scoped(s, VisibilityPrompt, data.prompt_id, p.id)
    values = data.model_dump(mode="json")
    values["prompt_snapshot"] = (
        data.prompt_snapshot if data.prompt_snapshot is not None else prompt.text
    )
    if data.observed_at:
        values["observed_at"] = data.observed_at.astimezone(timezone.utc).isoformat()
    identity = digest({**values, "supersedes_id": supersedes})
    duplicate = s.scalar(
        select(VisibilityObservation).where(
            VisibilityObservation.project_id == p.id,
            VisibilityObservation.identity == identity,
        )
    )
    if duplicate:
        return duplicate, False
    if (
        s.scalar(
            select(func.count())
            .select_from(VisibilityObservation)
            .where(VisibilityObservation.project_id == p.id)
        )
        >= LIMITS["observations"]
    ):
        fail("visibility_limit", "Đã đạt giới hạn quan sát cho project.")
    if supersedes:
        old = scoped(s, VisibilityObservation, supersedes, p.id)
        if s.scalar(
            select(VisibilityObservation.id).where(
                VisibilityObservation.supersedes_id == old.id
            )
        ):
            fail(
                "visibility_correction",
                "Quan sát đã có bản sửa; sửa từ phiên bản mới nhất.",
                409,
            )
    fields = {
        k: values[k]
        for k in (
            "prompt_id",
            "provider",
            "model",
            "collection_method",
            "prompt_snapshot",
            "response_text",
            "observed_at",
            "completeness",
            "citation_capability",
            "citation_metadata",
        )
    }
    brand_entities = [e for e in entities(s, p.id) if e["kind"] == "brand"]
    prompt_matches = extraction.mentions(values["prompt_snapshot"], brand_entities)
    branded = prompt.cohort_type == "brand_specific" or any(
        m["status"] != "REJECTED_MATCH" for m in prompt_matches
    )
    original = {k: v for k, v in values.items() if k not in fields}
    original["prompt_context"] = {
        "category": prompt.category,
        "intent": prompt.intent,
        "topic": prompt.data["topic"],
        "priority": prompt.priority,
        "declared_cohort_type": prompt.cohort_type,
        "cohort_type": "brand_specific" if branded else prompt.cohort_type,
        "branded_prompt_detected": bool(prompt_matches),
        "references": prompt.data,
    }
    original["correction_reason"] = reason
    original["import_provenance"] = (
        {"job_id": import_job.id, "file": import_job.data.get("file")}
        if import_job
        else None
    )
    row = VisibilityObservation(
        id=uid(),
        project_id=p.id,
        identity=identity,
        **fields,
        supersedes_id=supersedes,
        original=original,
        imported_at=now()
    )
    s.add(row)
    s.flush()
    extract(s, row)
    return row, True


def observation_view(s, row, full=True):
    revision = latest_extraction(s, row.id)
    detected = (
        list(
            s.scalars(
                select(VisibilityMention).where(
                    VisibilityMention.extraction_id == revision.id
                )
            )
        )
        if revision
        else []
    )
    citations = (
        list(
            s.scalars(
                select(VisibilityCitation).where(
                    VisibilityCitation.extraction_id == revision.id
                )
            )
        )
        if revision
        else []
    )
    result = {
        **view(row),
        "extraction": view(revision) if revision else None,
        "mentions": [view(m) for m in detected],
        "citations": [view(c) for c in citations],
        "missing_metadata": [
            k
            for k in ("model", "observed_at", "country", "language", "location")
            if not (getattr(row, k, None) or row.original.get(k))
        ],
        "corrections": list(
            s.scalars(
                select(VisibilityObservation.id).where(
                    VisibilityObservation.supersedes_id == row.id
                )
            )
        ),
        "limitations": LIMITATIONS,
    }
    if not full:
        result["response_text"] = row.response_text[:400]
        result["original"] = {
            k: row.original.get(k)
            for k in ("grounding", "country", "language", "location", "prompt_context")
        }
        if result["extraction"]:
            result["extraction"].pop("config_snapshot", None)
    return result


def review_mention(s, p, id, data):
    row = s.get(VisibilityMention, id)
    revision = s.get(VisibilityExtraction, row.extraction_id) if row else None
    if not revision:
        fail("visibility_not_found", "Không tìm thấy mention.", 404)
    observation = scoped(s, VisibilityObservation, revision.observation_id, p.id)
    if latest_extraction(s, observation.id).id != revision.id:
        fail("visibility_stale_review", "Hãy review phiên bản nhận diện mới nhất.", 409)
    s.add(
        VisibilityReview(
            id=uid(),
            project_id=p.id,
            entity_type="mention",
            entity_id=id,
            decision=data.status,
            data={
                "before": row.status,
                "reason": data.reason,
                "observation_id": observation.id,
            },
            created_at=now(),
        )
    )
    row.status = data.status
    return row


def save_document(s, p, data):
    values = data.model_dump(mode="json")
    if values["url"]:
        try:
            values["url"] = extraction.normalize_url(values["url"])
        except ValueError:
            fail("visibility_source", "URL nguồn không hợp lệ.")
    if data.entity_id:
        scoped(s, VisibilityEntity, data.entity_id, p.id)
    for id in data.prompt_ids:
        scoped(s, VisibilityPrompt, id, p.id)
    fields = {k: values.pop(k) for k in ("kind", "url", "content", "approved")}
    row = VisibilityDocument(
        id=uid(), project_id=p.id, **fields, data=values, created_at=now()
    )
    s.add(row)
    s.flush()
    return row


def save_coverage(s, p, data):
    requirement = scoped(s, VisibilityDocument, data.requirement_id, p.id)
    page = scoped(s, VisibilityDocument, data.page_id, p.id)
    if (
        requirement.kind != "topic_requirement"
        or page.kind != "page_content"
        or not requirement.approved
        or not page.approved
        or not page.url
    ):
        fail(
            "visibility_coverage",
            "Cần requirement và nội dung trang đã được người dùng duyệt, kèm URL trang.",
        )
    row = VisibilityCoverage(
        id=uid(), project_id=p.id, **data.model_dump(), created_at=now()
    )
    s.add(row)
    s.flush()
    return row
