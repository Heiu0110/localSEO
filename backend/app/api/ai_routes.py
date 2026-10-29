"""Agent-owned writes and read-only project tools behind existing CSRF protections."""

import json
from typing import Annotated
from fastapi import APIRouter, Depends, Query, Body, Request
from fastapi.routing import APIRoute
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy import select, func
from app.gsc.runtime import get_runtime
from app.db.models import Setting
from app.ai.models import (
    AIConversation,
    AIMessage,
    AIToolExecution,
    AIEvidence,
    AIRecommendation,
    AIUsage,
)
from app.ai.schemas import (
    AISettings,
    ConversationCreate,
    ConversationPatch,
    MessageCreate,
    Review,
    Confirmation,
)
from app.ai.common import uid, now, view, require, fail, redact
from app.ai.context import context, projects, project
from app.ai.tools import metadata
from app.ai.provider import (
    settings,
    save_settings,
    provider_state,
    OpenAIProvider,
    VALIDATION_KEY,
)
from app.ai.agent import spent_today


class SafeAIRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            try:
                return await original(request)
            except RequestValidationError:
                return JSONResponse(
                    status_code=422,
                    content={
                        "code": "ai_invalid_input",
                        "detail": "Dữ liệu AI Workspace không hợp lệ. Kiểm tra kiểu, giới hạn và các trường được hỗ trợ; không gửi khóa/token qua API này.",
                    },
                )

        return handler


router = APIRouter(prefix="/api/ai", tags=["AI Workspace"], route_class=SafeAIRoute)
Runtime = Annotated[object, Depends(get_runtime)]


def scoped_conversation(session, id, project_id=None):
    conv = require(session, AIConversation, id)
    if project_id and conv.project_id != project_id:
        fail(
            "ai_scope_violation",
            "Hội thoại thuộc website khác. Chọn đúng ngữ cảnh.",
            403,
        )
    return conv


def public_message(session, m):
    data = {
        k: v for k, v in m.data.items() if k not in ("settings_snapshot", "question")
    }
    evidence = list(
        session.scalars(select(AIEvidence).where(AIEvidence.message_id == m.id))
    )
    metrics = []
    for e in evidence:
        current = e.data["value_summary"].get("current")
        if isinstance(current, dict) and e.data["metric_scope"] == "site/byProperty":
            metrics.append(
                {
                    "evidence_id": e.id,
                    "source_type": e.source_type,
                    "period": {
                        "start": e.data["date_start"],
                        "end": e.data["date_end"],
                    },
                    "metrics": current,
                }
            )
    return {
        **view(m),
        "data": data,
        "evidence": [
            {k: v for k, v in e.data.items() if k != "value_summary"} for e in evidence
        ],
        "metrics": metrics,
        "tools": [
            view(x)
            for x in session.scalars(
                select(AIToolExecution)
                .where(AIToolExecution.message_id == m.id)
                .order_by(AIToolExecution.created_at)
            )
        ],
        "recommendations": [
            view(x)
            for x in session.scalars(
                select(AIRecommendation)
                .where(AIRecommendation.message_id == m.id)
                .order_by(AIRecommendation.created_at)
            )
        ],
    }


@router.get("/projects")
def list_projects(runtime: Runtime):
    return projects(runtime.db)


@router.get("/projects/{project_id}/context")
@router.get("/projects/{project_id}/sources")
def get_context(project_id: str, runtime: Runtime):
    return redact(context(runtime.db, project_id))


@router.get("/tools")
def list_tools():
    return metadata()


@router.get("/conversations")
def conversations(
    runtime: Runtime,
    project_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=50),
):
    project(runtime.db, project_id)
    with runtime.db.session() as s:
        query = select(AIConversation).where(AIConversation.project_id == project_id)
        return {
            "rows": [
                view(x)
                for x in s.scalars(
                    query.order_by(
                        AIConversation.saved.desc(), AIConversation.updated_at.desc()
                    )
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
            "total": s.scalar(select(func.count()).select_from(query.subquery())),
            "page": page,
            "page_size": page_size,
        }


@router.post("/conversations", status_code=201)
def create_conversation(data: ConversationCreate, runtime: Runtime):
    project(runtime.db, data.project_id)
    cfg = settings(runtime.db)
    with runtime.db.session.begin() as s:
        conv = AIConversation(
            id=uid(),
            project_id=data.project_id,
            title=redact(data.title),
            provider=data.provider,
            model=cfg.model if data.provider == "openai" else "deterministic-report-v1",
            saved=False,
            created_at=now(),
            updated_at=now(),
        )
        s.add(conv)
        s.flush()
        return view(conv)


@router.get("/conversations/{id}")
def conversation(
    id: str,
    runtime: Runtime,
    project_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=30),
):
    with runtime.db.session() as s:
        conv = scoped_conversation(s, id, project_id)
        q = select(AIMessage).where(AIMessage.conversation_id == id)
        messages = list(
            reversed(
                list(
                    s.scalars(
                        q.order_by(AIMessage.created_at.desc(), AIMessage.role.asc())
                        .offset((page - 1) * page_size)
                        .limit(page_size)
                    )
                )
            )
        )
        active = s.scalar(
            select(AIMessage.id).where(
                AIMessage.conversation_id == id,
                AIMessage.status.in_(["queued", "running"]),
            )
        )
        return {
            "conversation": view(conv),
            "messages": [public_message(s, x) for x in messages],
            "total_messages": s.scalar(select(func.count()).select_from(q.subquery())),
            "page": page,
            "active_turn": active,
        }


@router.patch("/conversations/{id}")
def patch_conversation(
    id: str, data: ConversationPatch, runtime: Runtime, project_id: str
):
    with runtime.db.session.begin() as s:
        conv = scoped_conversation(s, id, project_id)
        if data.title is not None:
            conv.title = redact(data.title)
        if data.saved is not None:
            conv.saved = data.saved
        conv.updated_at = now()
        return view(conv)


@router.post("/conversations/{id}/delete")
def delete_conversation(id: str, data: Confirmation, runtime: Runtime, project_id: str):
    if not data.confirm:
        fail(
            "ai_confirmation",
            "Xác nhận xóa hội thoại, bằng chứng tham chiếu và đề xuất của phiên. Usage vẫn được giữ để tính ngân sách.",
        )
    with runtime.db.session.begin() as s:
        conv = scoped_conversation(s, id, project_id)
        if s.scalar(
            select(AIMessage.id).where(
                AIMessage.conversation_id == id,
                AIMessage.status.in_(["queued", "running"]),
            )
        ):
            fail("ai_turn_active", "Chờ lượt hiện tại kết thúc trước khi xóa.", 409)
        s.delete(conv)
        return {"deleted": True, "usage_retained": True}


@router.post("/conversations/{id}/estimate")
def estimate(id: str, data: MessageCreate, runtime: Runtime, project_id: str):
    with runtime.db.session() as s:
        conv = scoped_conversation(s, id, project_id)
    _, result = runtime.ai.preflight(data.provider or conv.provider)
    return result


@router.post("/conversations/{id}/messages", status_code=202)
def message(id: str, data: MessageCreate, runtime: Runtime, project_id: str):
    with runtime.db.session() as s:
        scoped_conversation(s, id, project_id)
    m = runtime.ai.start(id, data)
    return {
        "id": m["id"],
        "status": m["status"],
        "conversation_id": id,
        "project_id": project_id,
    }


@router.get("/evidence/{id}")
def evidence(id: str, runtime: Runtime, project_id: str):
    with runtime.db.session() as s:
        e = require(s, AIEvidence, id)
        if e.project_id != project_id:
            fail("ai_scope_violation", "Bằng chứng thuộc website khác.", 403)
        return e.data


@router.get("/recommendations")
def recommendations(
    runtime: Runtime,
    project_id: str,
    conversation_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
):
    project(runtime.db, project_id)
    with runtime.db.session() as s:
        q = select(AIRecommendation).where(AIRecommendation.project_id == project_id)
        if conversation_id:
            scoped_conversation(s, conversation_id, project_id)
            q = q.where(AIRecommendation.conversation_id == conversation_id)
        return {
            "rows": [
                view(x)
                for x in s.scalars(
                    q.order_by(AIRecommendation.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
            ],
            "total": s.scalar(select(func.count()).select_from(q.subquery())),
        }


@router.patch("/recommendations/{id}")
def review(id: str, data: Review, runtime: Runtime, project_id: str):
    with runtime.db.session.begin() as s:
        rec = require(s, AIRecommendation, id)
        if rec.project_id != project_id:
            fail("ai_scope_violation", "Đề xuất thuộc website khác.", 403)
        rec.approval_status = data.approval_status
        rec.user_notes = redact(data.user_notes)
        rec.reviewed_at = now()
        rec.updated_at = now()
        return {**view(rec), "execution_triggered": False}


@router.get("/settings")
def get_settings(runtime: Runtime):
    return provider_state(runtime.db, runtime.ai.vault)


@router.patch("/settings")
def update_settings(runtime: Runtime, body: dict = Body()):
    try:
        value = AISettings.model_validate(
            {**settings(runtime.db).model_dump(mode="json"), **body}
        )
    except ValidationError:
        fail(
            "ai_settings_invalid",
            "Cấu hình AI chưa hợp lệ. Cần giới hạn hữu hạn, model ID đúng và giá/ngày kiểm tra khi bật OpenAI; không gửi API key qua UI.",
        )
    save_settings(runtime.db, value)
    return provider_state(runtime.db, runtime.ai.vault)


@router.post("/provider/test")
def validate_provider(runtime: Runtime):
    cfg = settings(runtime.db)
    result = runtime.ai.provider_factory().validate(cfg.model)
    with runtime.db.session.begin() as s:
        record = s.get(Setting, VALIDATION_KEY)
        if record:
            record.value = json.dumps(result)
        else:
            s.add(Setting(key=VALIDATION_KEY, value=json.dumps(result)))
    return {
        "validated": True,
        "model": result["model"],
        "validated_at": result["validated_at"],
        "paid_generation_requested": False,
        "note": "GET model xác minh key/quyền. Khả năng tool/schema cần kiểm chứng bằng lượt chat có xác nhận.",
    }


@router.get("/usage")
def usage(
    runtime: Runtime,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
):
    with runtime.db.session() as s:
        rows = [
            view(x)
            for x in s.scalars(
                select(AIUsage)
                .order_by(AIUsage.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        ]
        return {
            "rows": rows,
            "total": s.scalar(select(func.count()).select_from(AIUsage)),
            "daily_used_estimate_usd": spent_today(s),
            "daily_limit_usd": settings(runtime.db).daily_limit_usd,
            "day_timezone": "Asia/Ho_Chi_Minh",
            "pricing_status": "user_estimate",
            "provider_reported_dollar_cost": None,
            "note": "Tokens là usage provider nếu có; USD chỉ là ước tính theo giá bạn cấu hình. Request chưa xác định usage giữ khoản dự phòng. Không phải billing cap của OpenAI.",
        }
