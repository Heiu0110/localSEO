"""Single-user local AI Visibility APIs behind the existing CSRF/Origin controls."""

from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Query, UploadFile, File, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from sqlalchemy import select, func
from pydantic import ValidationError
from app.api.ai_routes import Runtime
from app.ai.common import view, now, uid, fail
from app.visibility.models import *
from app.visibility.schemas import *
from app.visibility import core, metrics, engine, files
from app.ai.schemas import MessageCreate
from app.ai.models import AIConversation


class PrivateVisibilityRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            try:
                response = await original(request)
            except (RequestValidationError, ValidationError):
                response = JSONResponse(
                    status_code=422,
                    content={
                        "code": "visibility_invalid_input",
                        "detail": "Dữ liệu Visibility không hợp lệ. Kiểm tra schema, trường bắt buộc, giới hạn và timezone; không gửi khóa hoặc token.",
                    },
                )
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        return handler


router = APIRouter(
    prefix="/api/visibility", tags=["AI Visibility"], route_class=PrivateVisibilityRoute
)
Scope = Annotated[Cohort, Depends()]


@router.get("/capabilities")
def capabilities():
    return {
        "release": "0.8 Core",
        "manual_entry": True,
        "import": ["json", "csv", "prompts_xlsx"],
        "live_collection": False,
        "providers": [
            {
                "id": name,
                "status": "not_connected",
                "reason": "Adapter live có citation thuộc v0.8.1/v0.8.2; không suy ra quyền từ ChatGPT login.",
            }
            for name in ("openai_web_search", "gemini_grounding")
        ],
        "limits": core.LIMITS,
        "limitations": core.LIMITATIONS,
        "rules": engine.catalog(),
    }


@router.get("/projects")
def projects(runtime: Runtime, local_project_id: str | None = None):
    with runtime.db.session() as s:
        q = select(VisibilityProject)
        if local_project_id:
            q = q.where(VisibilityProject.local_project_id == local_project_id)
        return [
            view(row)
            for row in s.scalars(
                q.order_by(VisibilityProject.updated_at.desc()).limit(100)
            )
        ]


@router.post("/projects", status_code=201)
def create_project(data: ProjectInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(core.new_project(s, runtime.db, data))


@router.patch("/projects/{id}")
def patch_project(id: str, data: ProjectPatch, runtime: Runtime):
    with runtime.db.session.begin() as s:
        row = core.project(s, id)
        for key, value in data.model_dump(exclude_unset=True).items():
            if value is None:
                fail("visibility_input", "Không chấp nhận null.")
            setattr(row, key, value)
        row.updated_at = now()
        return view(row)


@router.get("/entities")
def entities(project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        core.project(s, project_id)
        return core.entities(s, project_id)


@router.get("/brands")
def brands(project_id: str, runtime: Runtime):
    return [row for row in entities(project_id, runtime) if row["kind"] == "brand"]


@router.get("/competitors")
def competitors(project_id: str, runtime: Runtime):
    return [row for row in entities(project_id, runtime) if row["kind"] == "competitor"]


@router.post("/entities", status_code=201)
@router.post("/brands", status_code=201)
def create_entity(project_id: str, data: EntityInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(core.save_entity(s, core.project(s, project_id), data))


@router.post("/competitors", status_code=201)
def create_competitor(project_id: str, data: EntityInput, runtime: Runtime):
    return create_entity(
        project_id, data.model_copy(update={"kind": "competitor"}), runtime
    )


@router.patch("/entities/{id}")
@router.patch("/brands/{id}")
def edit_entity(id: str, project_id: str, data: EntityInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(core.save_entity(s, core.project(s, project_id), data, id))


@router.get("/prompts")
def prompts(
    project_id: str,
    runtime: Runtime,
    search: str = Query(default="", max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    with runtime.db.session() as s:
        core.project(s, project_id)
        q = select(VisibilityPrompt).where(
            VisibilityPrompt.project_id == project_id,
            VisibilityPrompt.text.contains(search, autoescape=True),
        )
        total = s.scalar(select(func.count()).select_from(q.subquery()))
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "rows": [
                core.prompt_view(row)
                for row in s.scalars(
                    q.order_by(VisibilityPrompt.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
        }


@router.get("/references")
def references(project_id: str, runtime: Runtime):
    from app.research.models import ResearchProject, ResearchKeyword, ResearchCluster
    from app.keywords.models import KeywordSet, TrackedKeyword

    with runtime.db.session() as s:
        p = core.project(s, project_id)
        projects = select(ResearchProject.id).where(
            ResearchProject.local_project_id == p.local_project_id
        )
        sets = select(KeywordSet.id).where(KeywordSet.site_id == p.local_project_id)
        return {
            "research_keywords": [
                {"id": x.id, "name": x.keyword_text}
                for x in s.scalars(
                    select(ResearchKeyword)
                    .where(ResearchKeyword.project_id.in_(projects))
                    .limit(200)
                )
            ],
            "research_clusters": [
                {"id": x.id, "name": x.name}
                for x in s.scalars(
                    select(ResearchCluster)
                    .where(ResearchCluster.project_id.in_(projects))
                    .limit(200)
                )
            ],
            "tracking": [
                {"id": x.id, "name": x.keyword_text}
                for x in s.scalars(
                    select(TrackedKeyword)
                    .where(TrackedKeyword.keyword_set_id.in_(sets))
                    .limit(200)
                )
            ],
            "topical_map_available": False,
            "bounded": True,
        }


@router.post("/prompts", status_code=201)
def create_prompt(project_id: str, data: PromptInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        row, created = core.save_prompt(s, core.project(s, project_id), data)
        return {**core.prompt_view(row), "created": created}


@router.patch("/prompts/{id}")
def edit_prompt(id: str, project_id: str, data: PromptInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        row, _ = core.save_prompt(s, core.project(s, project_id), data, id)
        return core.prompt_view(row)


@router.post("/{kind}/import-preview")
def import_preview(
    kind: Literal["prompts", "observations"],
    project_id: str,
    data: ImportPreview,
    runtime: Runtime,
):
    with runtime.db.session.begin() as s:
        return files.preview(s, core.project(s, project_id), kind, data.rows)


@router.post("/{kind}/file-preview")
async def file_preview(
    kind: Literal["prompts", "observations"],
    project_id: str,
    runtime: Runtime,
    file: UploadFile = File(...),
):
    content = await file.read(102401)
    rows = files.read_rows(content, file.filename or "", kind)
    with runtime.db.session.begin() as s:
        return files.preview(
            s,
            core.project(s, project_id),
            kind,
            rows,
            file={
                "name": (file.filename or "").replace("\\", "/").split("/")[-1][:200],
                "sha256": files.hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            },
        )


@router.post("/{kind}/import-commit")
def import_commit(
    kind: Literal["prompts", "observations"],
    project_id: str,
    data: ImportCommit,
    runtime: Runtime,
):
    if not data.confirm:
        fail("visibility_confirmation", "Cần xác nhận commit preview.", 409)
    with runtime.db.session.begin() as s:
        p = core.project(s, project_id)
        job = core.scoped(s, VisibilityImportJob, data.job_id, p.id)
        if job.kind != kind:
            fail("visibility_scope", "Loại preview không khớp.", 409)
        return files.commit(s, p, job.id)


@router.post("/prompts/from-sources-preview")
def source_prompts(project_id: str, data: SourcePrompts, runtime: Runtime):
    from app.research.models import ResearchKeyword, ResearchCluster, ResearchProject
    from app.keywords.models import TrackedKeyword, KeywordSet

    rows = []
    with runtime.db.session.begin() as s:
        p = core.project(s, project_id)
        for id in list(dict.fromkeys(data.ids)):
            model = {
                "research_keywords": ResearchKeyword,
                "research_clusters": ResearchCluster,
                "tracking": TrackedKeyword,
            }[data.source]
            item = s.get(model, id)
            source = (
                (
                    s.get(KeywordSet, item.keyword_set_id)
                    if data.source == "tracking"
                    else s.get(ResearchProject, item.project_id)
                )
                if item
                else None
            )
            site = (
                source.site_id
                if data.source == "tracking" and source
                else source.local_project_id if source else None
            )
            if site != p.local_project_id:
                fail(
                    "visibility_scope",
                    "Nguồn prompt không thuộc website của project.",
                    403,
                )
            row = {
                "text": (
                    item.name
                    if data.source == "research_clusters"
                    else item.keyword_text
                ),
                "topic": (
                    item.name
                    if data.source == "research_clusters"
                    else item.keyword_text
                ),
                "language": p.language,
                "country": p.country,
                "status": "draft",
                "source": "tracking" if data.source == "tracking" else "research",
                "notes": "Ứng viên prompt từ dữ liệu đã lưu; không phải observed user search demand.",
            }
            row[
                {
                    "research_keywords": "research_keyword_ids",
                    "research_clusters": "research_cluster_id",
                    "tracking": "tracking_keyword_id",
                }[data.source]
            ] = (
                [id] if data.source == "research_keywords" else id
            )
            rows.append(row)
        return files.preview(s, p, "prompts", rows)


@router.get("/observations")
def observations(
    project_id: str,
    runtime: Runtime,
    scope: Scope,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    with runtime.db.session() as s:
        p = core.project(s, project_id)
        rows, exclusions = metrics.selected(s, p, scope)
        return {
            "rows": [
                core.observation_view(s, row, False)
                for row in rows[(page - 1) * page_size : page * page_size]
            ],
            "total": len(rows),
            "page": page,
            "page_size": page_size,
            "excluded": exclusions,
        }


@router.post("/observations", status_code=201)
def create_observation(project_id: str, data: ObservationInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        row, created = core.ingest(s, core.project(s, project_id), data)
        return {**core.observation_view(s, row), "created": created}


@router.get("/observations/{id}")
def observation(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        row = core.scoped(s, VisibilityObservation, id, project_id)
        return core.observation_view(s, row)


@router.post("/observations/{id}/corrections", status_code=201)
def correct_observation(id: str, project_id: str, data: Correction, runtime: Runtime):
    with runtime.db.session.begin() as s:
        row, created = core.ingest(
            s,
            core.project(s, project_id),
            data.observation,
            supersedes=id,
            reason=data.reason,
        )
        return {**core.observation_view(s, row), "created": created}


@router.post("/observations/{id}/extract")
def reextract(id: str, project_id: str, data: Confirm, runtime: Runtime):
    if not data.confirm:
        fail("visibility_confirmation", "Cần xác nhận tạo revision nhận diện mới.", 409)
    with runtime.db.session.begin() as s:
        row = core.scoped(s, VisibilityObservation, id, project_id)
        core.extract(s, row)
        return core.observation_view(s, row)


@router.patch("/mentions/{id}/review")
def review_mention(id: str, project_id: str, data: MentionReview, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(core.review_mention(s, core.project(s, project_id), id, data))


@router.get("/overview")
@router.get("/competitors/compare")
def overview(project_id: str, runtime: Runtime, scope: Scope):
    with runtime.db.session() as s:
        return metrics.overview(s, core.project(s, project_id), scope)


@router.get("/mentions")
@router.get("/citations")
def extracted_records(
    project_id: str,
    runtime: Runtime,
    scope: Scope,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
):
    with runtime.db.session() as s:
        kind = "mentions" if request.url.path.endswith("/mentions") else "citations"
        p = core.project(s, project_id)
        rows, _ = metrics.selected(s, p, scope)
        result = [
            {
                **value,
                "observation_id": bundle["observation"].id,
                "prompt_id": bundle["observation"].prompt_id,
            }
            for bundle in metrics.bundles(s, rows)
            for value in bundle[kind]
        ]
        return {
            "rows": result[(page - 1) * page_size : page * page_size],
            "total": len(result),
            "page": page,
        }


@router.get("/documents")
def documents(project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        core.project(s, project_id)
        return [
            view(row)
            for row in s.scalars(
                select(VisibilityDocument)
                .where(VisibilityDocument.project_id == project_id)
                .order_by(VisibilityDocument.created_at.desc())
                .limit(200)
            )
        ]


@router.post("/documents", status_code=201)
def create_document(project_id: str, data: DocumentInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(core.save_document(s, core.project(s, project_id), data))


@router.patch("/documents/{id}/review")
def review_document(id: str, project_id: str, data: SourceReview, runtime: Runtime):
    with runtime.db.session.begin() as s:
        core.project(s, project_id)
        row = core.scoped(s, VisibilityDocument, id, project_id)
        s.add(
            VisibilityReview(
                id=uid(),
                project_id=project_id,
                entity_type="document",
                entity_id=id,
                decision="approved" if data.approved else "withdrawn",
                data={"before": row.approved, "reason": data.reason},
                created_at=now(),
            )
        )
        row.approved = data.approved
        return view(row)


@router.post("/coverage-reviews", status_code=201)
def coverage_review(project_id: str, data: CoverageInput, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return view(core.save_coverage(s, core.project(s, project_id), data))


@router.get("/opportunities")
def opportunities(
    project_id: str,
    runtime: Runtime,
    status: str = "",
    run_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    with runtime.db.session() as s:
        core.project(s, project_id)
        q = select(VisibilityOpportunity).where(
            VisibilityOpportunity.project_id == project_id
        )
        if status:
            q = q.where(VisibilityOpportunity.review_status == status)
        if run_id:
            run = core.scoped(s, VisibilityRun, run_id, project_id)
            q = q.where(VisibilityOpportunity.id.in_(run.data["opportunity_ids"]))
        total = s.scalar(select(func.count()).select_from(q.subquery()))
        return {
            "total": total,
            "rows": [
                engine.opportunity_view(s, row, full=False)
                for row in s.scalars(
                    q.order_by(VisibilityOpportunity.updated_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
            "page": page,
        }


@router.post("/opportunities/detect")
def detect_opportunities(project_id: str, data: Cohort, runtime: Runtime):
    with runtime.db.session.begin() as s:
        return engine.detect(s, runtime.db, core.project(s, project_id), data)


@router.get("/detection-runs")
def detection_runs(project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        core.project(s, project_id)
        return [
            view(row)
            for row in s.scalars(
                select(VisibilityRun)
                .where(VisibilityRun.project_id == project_id)
                .order_by(VisibilityRun.created_at.desc())
                .limit(20)
            )
        ]


@router.get("/opportunities/{id}")
def opportunity(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        row = core.scoped(s, VisibilityOpportunity, id, project_id)
        return {
            **engine.opportunity_view(s, row),
            "evidence": [
                view(core.scoped(s, VisibilityEvidence, eid, project_id))
                for eid in row.data["evidence_ids"] + row.data["seo_evidence_ids"]
            ],
        }


@router.get("/evidence/{id}")
def get_evidence(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        return view(core.scoped(s, VisibilityEvidence, id, project_id))


@router.patch("/opportunities/{id}/review")
def review_opportunity(
    id: str, project_id: str, data: OpportunityReview, runtime: Runtime
):
    with runtime.db.session.begin() as s:
        row = core.scoped(s, VisibilityOpportunity, id, project_id)
        s.add(
            VisibilityReview(
                id=uid(),
                project_id=project_id,
                entity_type="opportunity",
                entity_id=id,
                decision=data.status,
                data={"before": row.review_status, **data.model_dump()},
                created_at=now(),
            )
        )
        row.review_status, row.updated_at = data.status, now()
        row.data = {
            **row.data,
            "human_review": data.model_dump(),
            "approval_is_not_proof_or_execution": True,
        }
        return engine.opportunity_view(s, row)


class AnalyzeInput(Input):
    conversation_id: str = Field(min_length=1, max_length=100)
    message: MessageCreate


@router.post("/opportunities/{id}/analyze", status_code=202)
def analyze_opportunity(id: str, project_id: str, data: AnalyzeInput, runtime: Runtime):
    with runtime.db.session() as s:
        p = core.project(s, project_id)
        core.scoped(s, VisibilityOpportunity, id, p.id)
        conv = s.get(AIConversation, data.conversation_id)
        if not conv or conv.project_id != p.local_project_id:
            fail(
                "visibility_scope",
                "Hội thoại AI Workspace không thuộc website này.",
                403,
            )
        scope = GEOAnalysisScope(visibility_project_id=p.id, opportunity_id=id)
        if data.message.geo_scope and data.message.geo_scope != scope:
            fail("visibility_scope", "Scope phân tích không khớp opportunity.", 403)
        message = data.message.model_copy(update={"geo_scope": scope})
    # All existing model permissions, per-turn consent, cost and request guards
    # remain in AIManager.start; this endpoint cannot bypass them.
    return {
        "message": runtime.ai.start(conv.id, message),
        "conversation_id": conv.id,
        "workspace_url": f"/ai-workspace?project={p.local_project_id}&conversation={conv.id}&visibility={p.id}&geo={id}",
    }


@router.get("/export")
def export(
    project_id: str,
    runtime: Runtime,
    scope: Scope,
    kind: Literal[
        "observations", "prompts", "citations", "opportunities", "overview"
    ] = "observations",
    format: Literal["json", "csv"] = "json",
):
    with runtime.db.session() as s:
        p = core.project(s, project_id)
        if kind == "prompts":
            data = [
                core.prompt_view(row)
                for row in s.scalars(
                    select(VisibilityPrompt).where(VisibilityPrompt.project_id == p.id)
                )
            ]
        elif kind == "opportunities":
            data = [
                engine.opportunity_view(s, row)
                for row in s.scalars(
                    select(VisibilityOpportunity).where(
                        VisibilityOpportunity.project_id == p.id
                    )
                )
            ]
        elif kind == "overview":
            data = metrics.overview(s, p, scope)["groups"]
        else:
            rows, _ = metrics.selected(s, p, scope)
            if kind == "observations":
                data = [core.observation_view(s, row) for row in rows]
            else:
                data = [
                    {**c, "observation_id": b["observation"].id}
                    for b in metrics.bundles(s, rows)
                    for c in b["citations"]
                ]
        content, mime = files.export(
            {
                "project": view(p),
                "scope": scope.model_dump(mode="json"),
                "data": data,
                "limitations": core.LIMITATIONS,
            },
            format,
        )
        return Response(
            content,
            media_type=mime,
            headers={
                "Content-Disposition": f'attachment; filename="visibility-{kind}.{format}"',
                "X-Visibility-Scope": p.id,
            },
        )
