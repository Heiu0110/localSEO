"""Explicitly confirmed live research only; existing localhost/CSRF route boundary."""

from fastapi import APIRouter, Query
from sqlalchemy import select, func
from app.api.ai_routes import Runtime
from app.api.visibility_routes import PrivateVisibilityRoute
from app.ai.common import view, uid, now
from app.visibility import core
from app.visibility.live_models import CollectionRequest, SearchSource
from app.visibility.live_schemas import (
    LiveSettings,
    CollectionPreflight,
    CollectionConfirmation,
    ExtractionReview,
)
from app.visibility.models import VisibilityObservation, VisibilityReview

router = APIRouter(
    prefix="/api/visibility",
    tags=["AI Visibility live collection"],
    route_class=PrivateVisibilityRoute,
)


@router.get("/prompts/{id}")
def prompt(id: str, project_id: str, runtime: Runtime):
    from app.visibility.models import VisibilityPrompt

    with runtime.db.session() as s:
        return core.prompt_view(core.scoped(s, VisibilityPrompt, id, project_id))


@router.get("/providers")
@router.get("/providers/openai-web-search/capabilities")
def providers(runtime: Runtime):
    return runtime.visibility_live.state()


@router.patch("/providers/openai-web-search/settings")
def provider_settings(data: LiveSettings, runtime: Runtime):
    return runtime.visibility_live.save_settings(data)


@router.post("/providers/openai-web-search/validate-model")
def validate_model(runtime: Runtime):
    return runtime.visibility_live.validate_model()


@router.post("/collection/preflight", status_code=201)
def preflight(project_id: str, data: CollectionPreflight, runtime: Runtime):
    return runtime.visibility_live.preflight(project_id, data)


@router.post("/collection/requests/{id}/confirm", status_code=202)
def confirm(id: str, project_id: str, data: CollectionConfirmation, runtime: Runtime):
    return runtime.visibility_live.confirm(project_id, id, data)


@router.post("/collection/requests/{id}/cancel")
def cancel(id: str, project_id: str, runtime: Runtime):
    return runtime.visibility_live.cancel(project_id, id)


@router.get("/collection/requests")
def requests(
    project_id: str,
    runtime: Runtime,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=30),
):
    with runtime.db.session() as s:
        core.project(s, project_id)
        query = select(CollectionRequest).where(
            CollectionRequest.project_id == project_id
        )
        total = s.scalar(select(func.count()).select_from(query.subquery()))
        rows = []
        for row in s.scalars(
            query.order_by(CollectionRequest.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ):
            result = runtime.visibility_live.request_view(s, row)
            # Full immutable provider diagnostics are available only on scoped detail.
            result["result"] = {
                k: v for k, v in result["result"].items() if k != "provider_response"
            }
            rows.append(result)
        return {"rows": rows, "total": total, "page": page, "page_size": page_size}


@router.get("/collection/requests/{id}")
def request(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        row = core.scoped(s, CollectionRequest, id, project_id)
        return runtime.visibility_live.request_view(s, row)


@router.get("/collection/requests/{id}/sources")
def request_sources(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        core.scoped(s, CollectionRequest, id, project_id)
        return [
            view(row)
            for row in s.scalars(
                select(SearchSource).where(
                    SearchSource.request_id == id, SearchSource.project_id == project_id
                )
            )
        ]


@router.get("/observations/{id}/search-sources")
def sources(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        core.scoped(s, VisibilityObservation, id, project_id)
        return [
            view(row)
            for row in s.scalars(
                select(SearchSource).where(
                    SearchSource.observation_id == id,
                    SearchSource.project_id == project_id,
                )
            )
        ]


@router.get("/collection/usage")
def usage(project_id: str, runtime: Runtime):
    from app.ai.models import AIUsage

    with runtime.db.session() as s:
        core.project(s, project_id)
        rows = [
            {**view(u), "collection_request_id": request.id}
            for u, request in s.execute(
                select(AIUsage, CollectionRequest)
                .join(CollectionRequest, CollectionRequest.usage_id == AIUsage.id)
                .where(CollectionRequest.project_id == project_id)
                .order_by(AIUsage.created_at.desc())
                .limit(50)
            )
        ]
        state = runtime.visibility_live.state()
        return {
            "rows": rows,
            "global_api_daily_used_estimate_usd": state["daily_used_estimate_usd"],
            "effective_daily_limit_usd": state["effective_daily_limit_usd"],
            "same_ledger_as_ai_workspace": True,
            "provider_reported_dollar_cost": None,
            "not_billing_cap": True,
        }


@router.get("/observations/{id}/collection-review")
def reviews(id: str, project_id: str, runtime: Runtime):
    with runtime.db.session() as s:
        core.scoped(s, VisibilityObservation, id, project_id)
        revision = core.latest_extraction(s, id)
        rows = list(
            s.scalars(
                select(VisibilityReview)
                .where(
                    VisibilityReview.project_id == project_id,
                    VisibilityReview.entity_type == "live_extraction",
                    VisibilityReview.entity_id == id,
                )
                .order_by(VisibilityReview.created_at.desc())
                .limit(20)
            )
        )
        return {
            "current_extraction_id": revision.id if revision else None,
            "reviews": [view(row) for row in rows],
            "content_verified": False,
        }


@router.post("/observations/{id}/collection-review")
def review(id: str, project_id: str, data: ExtractionReview, runtime: Runtime):
    with runtime.db.session.begin() as s:
        row = core.scoped(s, VisibilityObservation, id, project_id)
        revision = core.latest_extraction(s, id)
        record = VisibilityReview(
            id=uid(),
            project_id=project_id,
            entity_type="live_extraction",
            entity_id=id,
            decision=data.decision,
            data={
                "reason": data.reason,
                "extraction_id": revision.id if revision else None,
                "registry_hash": revision.registry_hash if revision else None,
                "scope": "answer_mentions_citation_attribution_and_ownership",
                "source_content_verified": False,
                "approval_executes_changes": False,
            },
            created_at=now(),
        )
        s.add(record)
        s.flush()
        return view(record)
