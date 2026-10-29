"""Local research commands require the same CSRF and Origin protection as existing modules."""

import json
from typing import Literal
from fastapi import APIRouter, Query, UploadFile, File, Form
from fastapi.responses import Response
from sqlalchemy import select, func, delete
from app.api.ai_routes import Runtime
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.ai.common import now, view, fail, uid, redact, require
from app.research.models import *
from app.research.schemas import *
from app.research import core, analysis, serp, files
from app.research.responses import (
    ProjectOutput,
    KeywordOutput,
    KeywordPageOutput,
    JobOutput,
    ClusterOutput,
)


class SafeResearchRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={
                        "code": "research_invalid_input",
                        "detail": "Dữ liệu Research không hợp lệ. Kiểm tra trường bắt buộc, scope/kỳ, đơn vị, URL và giới hạn; không gửi API key/token qua API này.",
                    },
                )

        return handler


router = APIRouter(
    prefix="/api/research", tags=["Keyword Research"], route_class=SafeResearchRoute
)


def project(s, id):
    return require(s, ResearchProject, id)


def owned(s, model, id, pid):
    project(s, pid)
    return core.scoped(s, model, id, pid)


@router.get("/providers")
def providers():
    return {
        "providers": [
            {
                "id": x,
                "status": "available",
                "capabilities": ["stored_import"],
                "billing": "none",
                "credentials_required": False,
            }
            for x in [
                "seed",
                "stored_gsc",
                "stored_tracking",
                "stored_crawl",
                "csv_xlsx_json",
                "manual_serp",
            ]
        ]
        + [
            {
                "id": x,
                "status": "not_connected",
                "capabilities": [],
                "billing": "not_configured",
                "credentials_required": True,
                "reason": "Chưa triển khai adapter live trong v0.7 Core.",
            }
            for x in ["google_ads", "serp_api", "google_trends"]
        ],
        "limits": {
            "file_bytes": 102400,
            "keywords_per_project": 5000,
            "snapshots_per_project": 500,
            "results_per_snapshot": 100,
        },
        "limitations": core.LIMITATIONS,
    }


@router.get("/projects", response_model=list[ProjectOutput])
def projects(runtime: Runtime, local_project_id: str | None = None):
    with runtime.db.session() as s:
        q = select(ResearchProject)
        if local_project_id:
            q = q.where(ResearchProject.local_project_id == local_project_id)
        return [
            core.project_view(s, p)
            for p in s.scalars(q.order_by(ResearchProject.updated_at.desc()).limit(100))
        ]


@router.post("/projects", status_code=201, response_model=ProjectOutput)
def create_project(data: ProjectInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return core.project_view(s, core.new_project(s, runtime.db, data))


@router.get("/projects/{id}", response_model=ProjectOutput)
def get_project(id: str, runtime: Runtime):
    with runtime.db.session() as s:
        return core.project_view(s, project(s, id))


@router.patch("/projects/{id}")
def patch_project(id: str, data: ProjectPatch, runtime: Runtime):
    with runtime.db.session.begin() as s:
        p = project(s, id)
        values = data.model_dump(exclude_unset=True)
        if any(v is None for v in values.values()):
            fail("research_validation", "Không chấp nhận null.")
        settings = {
            **p.settings,
            **{k: v for k, v in values.items() if k in p.settings},
        }
        if settings["near_min"] > settings["near_max"]:
            fail("research_validation", "Khoảng Average Position không hợp lệ.")
        p.settings = settings
        for k, v in values.items():
            if k not in settings:
                setattr(p, k, v)
        p.updated_at = now()
        return core.project_view(s, p)


@router.post("/projects/{id}/duplicate", status_code=201)
def duplicate(id: str, data: Confirm, runtime: Runtime):
    if not data.confirm:
        fail("research_confirmation", "Cần xác nhận sao chép.")
    with runtime.db.session.begin() as s:
        p = project(s, id)
        new = core.new_project(
            s,
            runtime.db,
            ProjectInput(
                **{k: getattr(p, k) for k in ProjectInput.model_fields},
            ),
        )
        new.name = (p.name + " · bản sao")[:200]
        new.settings = dict(p.settings)
        clusters = {}
        for c in s.scalars(
            select(ResearchCluster).where(ResearchCluster.project_id == p.id)
        ):
            copy = ResearchCluster(
                **{
                    **view(c),
                    "id": uid(),
                    "project_id": new.id,
                    "primary_keyword_id": None,
                    "status": "draft",
                    "created_at": now(),
                    "updated_at": now(),
                }
            )
            s.add(copy)
            clusters[c.id] = copy.id
        s.flush()
        for k in s.scalars(
            select(ResearchKeyword).where(ResearchKeyword.project_id == p.id)
        ):
            copy = ResearchKeyword(
                **{
                    **view(k),
                    "id": uid(),
                    "project_id": new.id,
                    "cluster_id": clusters.get(k.cluster_id),
                    "status": "draft",
                    "created_at": now(),
                    "updated_at": now(),
                }
            )
            s.add(copy)
            s.flush()
            for source in s.scalars(
                select(ResearchSource).where(ResearchSource.keyword_id == k.id)
            ):
                new_src = ResearchSource(
                    **{**view(source), "id": uid(), "keyword_id": copy.id}
                )
                s.add(new_src)
                s.flush()
                for m in s.scalars(
                    select(ResearchMetric).where(ResearchMetric.source_id == source.id)
                ):
                    s.add(
                        ResearchMetric(
                            **{**view(m), "id": uid(), "source_id": new_src.id}
                        )
                    )
        core.event(
            s,
            new.id,
            "project",
            new.id,
            "duplicated",
            {
                "from": p.id,
                "note": "Copy keywords/clusters/sources as draft; snapshots, usage and reviews stay in original.",
            },
        )
        return core.project_view(s, new)


@router.post("/projects/{id}/delete")
def delete_project(id: str, data: Confirm, runtime: Runtime):
    if not data.confirm:
        fail("research_confirmation", "Cần xác nhận xóa dự án Research.")
    with runtime.db.session.begin() as s:
        s.delete(project(s, id))
        return {"deleted": True, "source_seo_data_untouched": True}


@router.get("/keywords", response_model=KeywordPageOutput)
def keywords(
    runtime: Runtime,
    project_id: str,
    search: str = Query("", max_length=200),
    status: Status | None = None,
    intent: Intent | None = None,
    group: str = Query("", max_length=100),
    brand: Literal["", "unknown", "branded", "non_branded"] = "",
    cluster_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    sort: Literal["keyword", "updated", "status"] = "keyword",
    direction: Literal["asc", "desc"] = "asc",
):
    with runtime.db.session() as s:
        project(s, project_id)
        q = select(ResearchKeyword).where(ResearchKeyword.project_id == project_id)
        if search:
            q = q.where(
                ResearchKeyword.normalized_keyword.contains(
                    normalize(search), autoescape=True
                )
            )
        if status:
            q = q.where(ResearchKeyword.status == status)
        if intent:
            q = q.where(ResearchKeyword.intent == intent)
        if group:
            q = q.where(ResearchKeyword.group_name == group)
        if brand:
            q = q.where(ResearchKeyword.brand_label == brand)
        if cluster_id:
            q = q.where(
                ResearchKeyword.cluster_id
                == owned(s, ResearchCluster, cluster_id, project_id).id
            )
        col = {
            "keyword": ResearchKeyword.normalized_keyword,
            "updated": ResearchKeyword.updated_at,
            "status": ResearchKeyword.status,
        }[sort]
        count = s.scalar(select(func.count()).select_from(q.subquery()))
        rows = list(
            s.scalars(
                q.order_by(
                    col.desc() if direction == "desc" else col.asc(), ResearchKeyword.id
                )
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
        return {
            "rows": core.keyword_views(s, rows),
            "total": count,
            "page": page,
            "page_size": page_size,
        }


@router.get("/keywords/{id}", response_model=KeywordOutput)
def keyword(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        k = owned(s, ResearchKeyword, id, project_id)
        p = project(s, project_id)
        return {
            **core.keyword_views(s, [k])[0],
            "intent_suggestion": core.intent_suggestion(k),
            "target_suggestions": analysis.target_suggestions(runtime.db, s, p, k),
            "reviews": [
                view(x)
                for x in s.scalars(
                    select(ResearchReview)
                    .where(
                        ResearchReview.project_id == p.id,
                        ResearchReview.entity_id == id,
                    )
                    .order_by(ResearchReview.created_at.desc())
                    .limit(50)
                )
            ],
        }


@router.patch("/keywords/{id}")
def update_keyword(id: str, project_id: str, data: KeywordPatch, runtime: Runtime):
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        k = owned(s, ResearchKeyword, id, p.id)
        core.patch_keyword(s, p, k, data)
        return view(k)


@router.post("/keywords/bulk")
def bulk(project_id: str, data: Bulk, runtime: Runtime):
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        for id in dict.fromkeys(data.ids):
            core.patch_keyword(s, p, owned(s, ResearchKeyword, id, p.id), data.changes)
        return {"updated": len(set(data.ids))}


@router.post("/discovery/preview", response_model=JobOutput)
def discovery(project_id: str, data: Discovery, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return core.discover(runtime.db, s, project(s, project_id), data)


@router.post("/import/preview", response_model=JobOutput)
async def import_file(
    runtime: Runtime,
    project_id: str = Form(...),
    kind: Literal["keywords", "serp"] = Form("keywords"),
    mapping: str = Form("{}"),
    file: UploadFile = File(...),
):
    content = await file.read(102401)
    try:
        mapped = json.loads(mapping)
        if not isinstance(mapped, dict):
            raise ValueError()
    except Exception:
        fail("research_mapping", "Mapping cần JSON object.")
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        if kind == "serp":
            raw = files.read_serp(content, file.filename or "")
            owned(s, ResearchKeyword, raw["keyword_id"], p.id)
            return core.preview(s, p, [raw], "serp")
        rows, meta = files.read_keywords(content, file.filename or "", p, mapped)
        return core.discover(
            runtime.db, s, p, Discovery(source="rows", rows=rows, limit=1000)
        ) | {"file_mapping": meta}


@router.post("/import/{id}/commit")
def commit(id: str, project_id: str, data: Confirm, runtime: Runtime):
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        job = owned(s, ResearchJob, id, p.id)
        return core.commit_job(s, p, job, data.confirm)


@router.get("/clusters", response_model=list[ClusterOutput])
def clusters(project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        project(s, project_id)
        return [
            analysis.cluster_view(s, c)
            for c in s.scalars(
                select(ResearchCluster)
                .where(ResearchCluster.project_id == project_id)
                .order_by(ResearchCluster.name)
                .limit(500)
            )
        ]


@router.post("/clusters", status_code=201)
def create_cluster(project_id: str, data: ClusterInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return analysis.cluster_view(
            s, core.create_cluster(s, project(s, project_id), data)
        )


@router.post("/clusters/suggest")
def suggest(project_id: str, data: Suggest, runtime: Runtime):
    with runtime.db.session() as s:
        return analysis.suggest(s, project(s, project_id), data.method)


@router.patch("/clusters/{id}")
def patch_cluster(id: str, project_id: str, data: ClusterPatch, runtime: Runtime):
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        core.writable(p)
        c = owned(s, ResearchCluster, id, p.id)
        before = view(c)
        values = data.model_dump(exclude_unset=True)
        if any(v is None for k, v in values.items() if k != "primary_keyword_id"):
            fail("research_validation", "Không chấp nhận null.")
        primary = values.get("primary_keyword_id", c.primary_keyword_id)
        if primary and owned(s, ResearchKeyword, primary, p.id).cluster_id != c.id:
            fail("research_primary", "Primary cần thuộc cluster.")
        if values.get("mapping_status", c.mapping_status) in (
            "approved",
            "planned",
        ) and not values.get("target_url", c.target_url):
            fail("research_mapping", "Mapping cần URL.")
        for k, v in values.items():
            setattr(c, k, v)
        c.updated_at = now()
        core.event(
            s, p.id, "cluster", c.id, c.status, {"before": before, "after": view(c)}
        )
        return analysis.cluster_view(s, c)


@router.post("/clusters/{id}/operation")
def cluster_operation(
    id: str, project_id: str, data: ClusterOperation, runtime: Runtime
):
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        core.writable(p)
        c = owned(s, ResearchCluster, id, p.id)
        if not data.confirm:
            fail("research_confirmation", "Cần xác nhận thay đổi cluster.")
        ids = list(dict.fromkeys(data.keyword_ids))
        members = [owned(s, ResearchKeyword, k, p.id) for k in ids]
        if data.operation == "delete":
            core.event(s, p.id, "cluster", c.id, "deleted", {"before": view(c)})
            s.delete(c)
            return {"deleted": True}
        if data.operation == "merge":
            dest = owned(s, ResearchCluster, data.destination_id or "", p.id)
            if dest.id == c.id:
                fail("research_cluster", "Không merge vào chính cluster.")
            members = list(
                s.scalars(
                    select(ResearchKeyword).where(ResearchKeyword.cluster_id == c.id)
                )
            )
            s.delete(c)
        elif data.operation == "split":
            if not members or any(k.cluster_id != c.id for k in members):
                fail("research_cluster", "Chọn thành viên của cluster để tách.")
            dest = core.create_cluster(
                s, p, ClusterInput(name=data.name, keyword_ids=ids)
            )
            c.status = "needs_review"
            c.primary_keyword_id = None
        else:
            dest = c
        for k in members:
            if k.cluster_id and k.cluster_id != dest.id:
                old = s.get(ResearchCluster, k.cluster_id)
                if old:
                    old.status = "needs_review"
                    if old.primary_keyword_id == k.id:
                        old.primary_keyword_id = None
            k.cluster_id = dest.id
            k.updated_at = now()
        dest.status = "needs_review"
        dest.updated_at = now()
        core.event(
            s,
            p.id,
            "cluster",
            dest.id,
            data.operation,
            {"keyword_ids": [k.id for k in members]},
        )
        return analysis.cluster_view(s, dest)


@router.post("/serp/import")
def serp_import(project_id: str, data: SerpInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        owned(s, ResearchKeyword, data.keyword_id, p.id)
        return core.preview(s, p, [data.model_dump(mode="json")], "serp")


@router.get("/serp/snapshots")
def snapshots(
    project_id: str,
    runtime: Runtime,
    keyword_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    with runtime.db.session() as s:
        project(s, project_id)
        q = select(SerpSnapshot).where(SerpSnapshot.project_id == project_id)
        if keyword_id:
            q = q.where(
                SerpSnapshot.keyword_id
                == owned(s, ResearchKeyword, keyword_id, project_id).id
            )
        return {
            "rows": [
                {
                    **view(x),
                    "keyword_text": s.get(ResearchKeyword, x.keyword_id).keyword_text,
                }
                for x in s.scalars(
                    q.order_by(SerpSnapshot.collected_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
            "total": s.scalar(select(func.count()).select_from(q.subquery())),
            "page": page,
        }


@router.get("/serp/compare")
def compare(project_id: str, a: str, b: str, runtime: Runtime):
    with runtime.db.session() as s:
        return serp.compare(s, project(s, project_id), a, b)


@router.get("/serp/snapshots/{id}")
def snapshot(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        return serp.snapshot_view(s, owned(s, SerpSnapshot, id, project_id), runtime.db)


@router.post("/serp/check")
def provider_check(data: Confirm):
    fail(
        "research_provider_unavailable",
        "Chưa kết nối provider SERP được xác minh. Nhập snapshot thủ công/tệp; không có request trả phí.",
        409,
    )


@router.get("/competitors")
def competitors(project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        return serp.competitors(s, project(s, project_id))


@router.post("/opportunities/refresh")
def refresh(project_id: str, data: Confirm, runtime: Runtime):
    if not data.confirm:
        fail("research_confirmation", "Cần xác nhận phân tích.")
    with runtime.db.session.begin() as s:
        p = project(s, project_id)
        core.writable(p)
        return analysis.refresh_opportunities(s, p)


@router.get("/opportunities")
def opportunities(
    project_id: str,
    runtime: Runtime,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    with runtime.db.session() as s:
        project(s, project_id)
        q = select(ResearchOpportunity).where(
            ResearchOpportunity.project_id == project_id
        )
        return {
            "rows": [
                {
                    **view(x),
                    "keyword_text": s.get(ResearchKeyword, x.keyword_id).keyword_text,
                }
                for x in s.scalars(
                    q.order_by(
                        ResearchOpportunity.updated_at.desc(), ResearchOpportunity.id
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
            "total": s.scalar(select(func.count()).select_from(q.subquery())),
            "page": page,
        }


@router.patch("/opportunities/{id}")
def review_opportunity(id: str, project_id: str, data: Review, runtime: Runtime):
    with runtime.db.session.begin() as s:
        core.writable(project(s, project_id))
        o = owned(s, ResearchOpportunity, id, project_id)
        o.status = data.status
        o.notes = data.notes
        o.updated_at = now()
        core.event(s, project_id, "opportunity", id, data.status, data.model_dump())
        return view(o)


@router.post("/export/keyword-tracking-preview")
def transfer(project_id: str, data: Transfer, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return core.transfer_preview(s, project(s, project_id), data)


@router.get("/export")
def export(
    project_id: str,
    runtime: Runtime,
    kind: Literal[
        "keywords",
        "clusters",
        "serp",
        "competitors",
        "opportunities",
        "topical_compatibility",
    ] = "keywords",
    format: Literal["csv", "xlsx", "json"] = "json",
    snapshot_id: str | None = None,
):
    with runtime.db.session() as s:
        p = project(s, project_id)
        if kind == "keywords":
            rows = list(
                s.scalars(
                    select(ResearchKeyword)
                    .where(ResearchKeyword.project_id == p.id)
                    .order_by(ResearchKeyword.normalized_keyword)
                    .limit(5000)
                )
            )
            data = []
            for k in core.keyword_views(s, rows):
                if format == "json":
                    for source in k["sources"]:
                        data.append(
                            {
                                key: value
                                for key, value in k.items()
                                if key in Candidate.model_fields and key != "metrics"
                            }
                            | {
                                "provider": source["provider"],
                                "method": source["method"],
                                "reference": source["reference"],
                                "seed": source["seed"],
                                "collected_at": source["collected_at"],
                                "metrics": source["metrics"],
                                "metadata": source["data"].get("metadata", {}),
                            }
                        )
                else:
                    data.append(k)
        elif kind in ("clusters", "topical_compatibility"):
            data = [
                analysis.cluster_view(s, c)
                for c in s.scalars(
                    select(ResearchCluster)
                    .where(ResearchCluster.project_id == p.id)
                    .limit(500)
                )
            ]
        elif kind == "serp":
            data = serp.snapshot_view(
                s, owned(s, SerpSnapshot, snapshot_id or "", p.id)
            )
        elif kind == "competitors":
            data = serp.competitors(s, p)
        else:
            data = [
                view(x)
                for x in s.scalars(
                    select(ResearchOpportunity)
                    .where(ResearchOpportunity.project_id == p.id)
                    .limit(10000)
                )
            ]
        content, mime = files.export_file(data, format)
        return Response(
            content,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="research-{kind}.{format}"',
                "X-Research-Scope": p.id,
            },
        )
