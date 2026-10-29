"""One fixed HTTPS provider. Keys never enter API responses, SQLite or browser code."""

import json
import time
from decimal import Decimal
from typing import Protocol
from urllib.parse import quote
import httpx
from app.db.models import Setting
from app.gsc.errors import GSCError
from .schemas import AISettings
from .common import fail, now

KEY_NAME = "ai.openai.api_key"
SETTINGS_KEY = "ai.settings.v1"
VALIDATION_KEY = "ai.openai.validated_model"
OFFICIAL_MODELS_SOURCE = "https://github.com/openai/openai-python/blob/main/src/openai/types/shared/chat_model.py"
PRICING_SOURCE = "https://openai.com/api/pricing/"


def settings(db):
    with db.session() as s:
        item = s.get(Setting, SETTINGS_KEY)
        return AISettings.model_validate_json(item.value) if item else AISettings()


def save_settings(db, value):
    previous = settings(db)
    with db.session.begin() as s:
        record = s.get(Setting, SETTINGS_KEY)
        raw = value.model_dump_json()
        if record:
            record.value = raw
        else:
            s.add(Setting(key=SETTINGS_KEY, value=raw))
        if previous.model != value.model:
            existing = s.get(Setting, VALIDATION_KEY)
            if existing:
                s.delete(existing)


def provider_state(db, vault):
    secure = True
    configured = False
    try:
        configured = bool((vault.get(KEY_NAME) or {}).get("api_key"))
    except GSCError:
        secure = False
    value = settings(db)
    with db.session() as s:
        record = s.get(Setting, VALIDATION_KEY)
    return {
        "settings": value.model_dump(mode="json"),
        "provider": "openai",
        "key_configured": configured,
        "secure_storage_available": secure,
        "model_validated": bool(
            record and json.loads(record.value).get("model") == value.model
        ),
        "model_reference": OFFICIAL_MODELS_SOURCE,
        "pricing_reference": PRICING_SOURCE,
        "pricing_status": (
            "user_estimate" if value.input_usd_per_million is not None else "unverified"
        ),
        "pricing_note": "Không xác minh được giá hiện hành từ trang OpenAI trong môi trường triển khai. Nhập giá đã kiểm tra; đây vẫn là ước tính do người dùng cấu hình.",
        "local_mode": "Báo cáo theo quy tắc từ dữ liệu lưu, không phải mô hình AI/offline LLM.",
    }


class ModelProvider(Protocol):
    def respond(self, payload: dict) -> dict: ...


class OpenAIProvider:
    endpoint = "https://api.openai.com/v1"

    def __init__(self, vault, transport=None):
        self.vault = vault
        self.transport = transport

    def _key(self):
        raw = self.vault.get(KEY_NAME) or {}
        key = raw.get("api_key")
        if not key:
            fail(
                "ai_key_missing",
                "Chưa cấu hình API key trong kho khóa hệ điều hành. Xem AI Settings.",
                409,
            )
        return key

    def request(self, method, path, body=None):
        key = self._key()
        for attempt in range(2):
            try:
                with httpx.Client(
                    transport=self.transport,
                    timeout=httpx.Timeout(30, connect=8, write=10, pool=5),
                    trust_env=False,
                    follow_redirects=False,
                ) as client:
                    with client.stream(
                        method,
                        self.endpoint + path,
                        headers={
                            "Authorization": "Bearer " + key,
                            "Content-Type": "application/json",
                        },
                        json=body,
                    ) as response:
                        status = response.status_code
                        if status == 429 and attempt == 0:
                            delay = response.headers.get("Retry-After", "1")
                            if delay.isdigit() and int(delay) <= 2:
                                time.sleep(int(delay))
                                continue
                        if status in (401, 403):
                            fail(
                                "ai_provider_auth",
                                "OpenAI từ chối key/quyền model. Kiểm tra lại cấu hình.",
                                409,
                            )
                        if status == 429:
                            fail(
                                "ai_provider_quota",
                                "OpenAI đang giới hạn quota/rate limit. Không tự gửi lặp nhiều lần.",
                                429,
                            )
                        if not 200 <= status < 300:
                            fail(
                                "ai_provider_error",
                                "Provider chưa xử lý được yêu cầu hoặc model không hỗ trợ Responses/tool/schema. Không tự retry để tránh tính phí trùng.",
                                502,
                            )
                        data = bytearray()
                        start = time.monotonic()
                        for chunk in response.iter_bytes():
                            data.extend(chunk)
                            if len(data) > 512 * 1024 or time.monotonic() - start > 45:
                                fail(
                                    "ai_provider_limit",
                                    "Phản hồi vượt kích thước/thời gian cho phép.",
                                    502,
                                )
                        try:
                            return json.loads(data)
                        except (ValueError, UnicodeError):
                            fail(
                                "ai_provider_invalid",
                                "Provider trả phản hồi không hợp lệ.",
                                502,
                            )
            except GSCError:
                raise
            except httpx.HTTPError:
                fail(
                    "ai_provider_network",
                    "Không kết nối được OpenAI hoặc request hết thời gian. Chi phí có thể chưa xác định; không tự retry.",
                    503,
                )

    def validate(self, model):
        result = self.request("GET", "/models/" + quote(model, safe=""))
        if result.get("id") != model:
            fail(
                "ai_provider_model",
                "Model chưa được xác thực với API key hiện tại.",
                409,
            )
        return {
            "model": model,
            "validated_at": now(),
            "capabilities": "Model tồn tại và key có quyền truy cập; Responses/tool/schema vẫn cần kiểm chứng bằng lượt chat được cho phép.",
        }

    def respond(self, payload):
        return self.request("POST", "/responses", payload)


def estimated_cost(input_tokens, output_tokens, value):
    if value.input_usd_per_million is None or value.output_usd_per_million is None:
        fail(
            "ai_pricing_missing",
            "Cần nhập giá ước tính của model trước khi gọi AI.",
            409,
        )
    return float(
        (
            Decimal(input_tokens) * Decimal(str(value.input_usd_per_million))
            + Decimal(output_tokens) * Decimal(str(value.output_usd_per_million))
        )
        / Decimal(1000000)
    )


def turn_estimate(value):
    # UTF-8 byte cap + protocol margin is a conservative input-token bound, not token usage.
    per_call = estimated_cost(
        value.max_context_bytes + 4096, value.max_output_tokens, value
    )
    return {
        "max_calls": value.max_tool_calls + 2,
        "per_call_reserved_usd": per_call,
        "turn_upper_estimate_usd": round(per_call * (value.max_tool_calls + 2), 8),
        "pricing_status": "user_estimate",
        "currency": "USD",
        "not_billing_cap": True,
    }
