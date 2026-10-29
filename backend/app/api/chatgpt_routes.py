"""SIWC commands share localhost Origin/CSRF; tokens never cross the frontend API."""

from fastapi import APIRouter
from pydantic import Field
from app.api.ai_routes import Runtime, SafeAIRoute
from app.ai.schemas import Input


class PrivateChatGPTRoute(SafeAIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request):
            response = await original(request)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Referrer-Policy"] = "no-referrer"
            return response

        return handler


router = APIRouter(
    prefix="/api/ai/chatgpt",
    tags=["ChatGPT Connection"],
    route_class=PrivateChatGPTRoute,
)


class Connect(Input):
    eligibility_acknowledged: bool = False
    localhost_acknowledged: bool = False


class SelectModel(Input):
    slug: str = Field(min_length=1, max_length=150)


class Disconnect(Input):
    confirm: bool
    revoke: bool = True


@router.get("/status")
def status(runtime: Runtime):
    return runtime.ai.chatgpt.status()


@router.post("/connect")
def connect(data: Connect, runtime: Runtime):
    return runtime.ai.chatgpt.start(
        data.eligibility_acknowledged, data.localhost_acknowledged
    )


@router.post("/models/refresh")
def models(runtime: Runtime):
    return runtime.ai.chatgpt.refresh_models()


@router.patch("/model")
def model(data: SelectModel, runtime: Runtime):
    return runtime.ai.chatgpt.select_model(data.slug)


@router.post("/disconnect")
def disconnect(data: Disconnect, runtime: Runtime):
    from app.ai.common import fail

    if not data.confirm:
        fail("chatgpt_confirmation", "Cần xác nhận ngắt kết nối ChatGPT.", 409)
    return runtime.ai.chatgpt.disconnect(data.revoke)
