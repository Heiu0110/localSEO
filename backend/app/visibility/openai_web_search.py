"""One-shot paid transport. Reuses existing OS-vault key; never SIWC, redirects or retries."""

import time
import hashlib
import httpx
from app.ai.provider import OpenAIProvider
from app.gsc.errors import GSCError
from .provider_contracts import ProviderCapabilities
from .live_schemas import INSTRUCTION, CONTRACT_VERSION
from .live_parser import strict_json, MAX_RESPONSE_BYTES, parse_response


class LiveProviderError(GSCError):
    def __init__(
        self,
        code,
        detail,
        status=502,
        *,
        uncertain=True,
        capability=None,
        submitted=True,
    ):
        super().__init__(code, detail, status)
        self.uncertain = uncertain
        self.submitted = submitted
        self.capability = capability


class OpenAIWebSearchVisibilityAdapter(OpenAIProvider):
    def capabilities(self):
        try:
            configured = bool(self._key())
        except GSCError:
            configured = False
        return ProviderCapabilities(
            "openai_web_search",
            configured,
            None,
            None,
            False,
            "Quyền Web Search cần lượt kiểm tra được xác nhận; model access không đủ.",
        )

    def payload(self, *, prompt_snapshot, settings, context):
        location = {
            "type": "approximate",
            **{k: context[k] for k in ("country", "city", "region") if context.get(k)},
        }
        instruction = INSTRUCTION + (
            " Requested response language: " + context["language"] + "."
            if context.get("language")
            else ""
        )
        return {
            "model": settings.model,
            "store": False,
            "stream": False,
            "input": [{"role": "user", "content": prompt_snapshot}],
            "instructions": instruction,
            "tools": [
                {
                    "type": "web_search",
                    "external_web_access": True,
                    "search_context_size": settings.search_context_size,
                    "user_location": location,
                }
            ],
            "tool_choice": "required",
            "max_tool_calls": settings.max_tool_calls,
            "max_output_tokens": settings.max_output_tokens,
            "include": ["web_search_call.action.sources"],
        }

    def observe(
        self,
        *,
        prompt_snapshot,
        consent_receipt_id,
        settings,
        context,
        prompt_id,
        collection_request_id,
        credential_tag,
    ):
        raw = self._send(
            prompt_snapshot=prompt_snapshot,
            consent_receipt_id=consent_receipt_id,
            settings=settings,
            context=context,
            credential_tag=credential_tag,
        )
        try:
            parsed = parse_response(
                raw,
                collection_request_id,
                prompt_id,
                prompt_snapshot,
                context,
                settings.model,
                {
                    "search_context_size": settings.search_context_size,
                    "max_tool_calls": settings.max_tool_calls,
                    "max_output_tokens": settings.max_output_tokens,
                    "external_web_access": True,
                },
            )
            if parsed["web_search_call_count"] > settings.max_tool_calls:
                parsed["problems"].append("provider_tool_limit_exceeded")
                parsed["status"], parsed["eligible"] = "PARTIAL", False
                if parsed["candidate"]:
                    candidate = parsed["candidate"]
                    parsed["candidate"] = candidate.model_copy(
                        update={
                            "completeness": "partial",
                            "citation_metadata": "partial",
                            "source_metadata": {
                                **candidate.source_metadata,
                                "normalization_notes": [
                                    *candidate.source_metadata["normalization_notes"],
                                    "provider_tool_limit_exceeded",
                                ],
                            },
                        }
                    )
            return {"raw_response": raw, "parsed": parsed, "normalization_error": None}
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            return {
                "raw_response": raw,
                "parsed": None,
                "normalization_error": "live_response_normalization_failed",
            }

    def _send(
        self, *, prompt_snapshot, consent_receipt_id, settings, context, credential_tag
    ):
        if not consent_receipt_id:
            raise LiveProviderError(
                "live_consent_missing", "Thiếu consent receipt.", 409, uncertain=False
            )
        payload = self.payload(
            prompt_snapshot=prompt_snapshot, settings=settings, context=context
        )
        key = self._key()
        if hashlib.sha256(key.encode()).hexdigest() != credential_tag:
            raise LiveProviderError(
                "live_credentials_changed",
                "Credential đã đổi sau consent; chưa gửi provider. Tạo preflight mới.",
                409,
                uncertain=False,
                submitted=False,
            )
        start = time.monotonic()
        try:
            with httpx.Client(
                transport=self.transport,
                timeout=httpx.Timeout(45, connect=8, write=10, pool=5),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                with client.stream(
                    "POST",
                    "https://api.openai.com/v1/responses",
                    headers={
                        "Authorization": "Bearer " + key,
                        "Content-Type": "application/json",
                    },
                    json=payload,
                ) as response:
                    if not 200 <= response.status_code < 300:
                        statuses = {
                            400: (
                                "live_request_unsupported",
                                "Model/cấu hình Web Search chưa được hỗ trợ.",
                                "Web Search Unsupported",
                            ),
                            401: (
                                "live_key_invalid",
                                "OpenAI từ chối API key.",
                                "Permission Denied",
                            ),
                            403: (
                                "live_permission_denied",
                                "Tài khoản/model chưa có quyền Web Search.",
                                "Permission Denied",
                            ),
                            429: (
                                "live_quota_limited",
                                "OpenAI giới hạn quota/rate; không tự gửi lại.",
                                "Quota Limited",
                            ),
                        }
                        code, message, cap = statuses.get(
                            response.status_code,
                            (
                                "live_provider_error",
                                "OpenAI chưa xử lý được yêu cầu; không tự retry.",
                                None,
                            ),
                        )
                        raise LiveProviderError(
                            code,
                            message,
                            (
                                response.status_code
                                if response.status_code in (400, 401, 403, 429)
                                else 502
                            ),
                            uncertain=response.status_code >= 500,
                            capability=cap,
                        )
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        if (
                            len(data) > MAX_RESPONSE_BYTES
                            or time.monotonic() - start > 60
                        ):
                            raise LiveProviderError(
                                "live_response_limit",
                                "Phản hồi vượt kích thước/thời gian; outcome/chi phí chưa xác định.",
                            )
                    try:
                        return strict_json(data)
                    except (ValueError, UnicodeError, RecursionError):
                        raise LiveProviderError(
                            "live_invalid_json",
                            "Phản hồi provider không phải JSON hợp lệ.",
                        )
        except httpx.HTTPError:
            raise LiveProviderError(
                "live_network_unknown",
                "Kết nối bị ngắt/timeout. Provider có thể đã tính phí; không tự chạy lại.",
                503,
            )
