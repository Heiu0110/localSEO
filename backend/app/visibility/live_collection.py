"""Single-prompt queue, immutable consent and shared AI dollar ledger. No replay/scheduler."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from app.db.models import Setting
from app.ai.models import AIUsage
from app.ai.provider import KEY_NAME, settings as ai_settings
from app.ai.agent import spent_today
from app.ai.common import uid, now, view, redact
from app.ai.context import project as local_project
from app.gsc.errors import GSCError
from . import core, live_costs
from .models import VisibilityProject, VisibilityPrompt, VisibilityReview
from .live_models import CollectionRequest, CollectionConsent, SearchSource
from .live_schemas import *
from .openai_web_search import OpenAIWebSearchVisibilityAdapter, LiveProviderError

TERMINAL = {
    "COMPLETED",
    "PARTIAL",
    "FAILED",
    "UNKNOWN_REMOTE_OUTCOME",
    "INTERRUPTED",
    "CANCELLED_BEFORE_SUBMISSION",
}


def load_settings(db):
    with db.session() as s:
        row = s.get(Setting, SETTINGS_KEY)
        return LiveSettings.model_validate_json(row.value) if row else LiveSettings()


def setting_write(s, key, data):
    row = s.get(Setting, key)
    value = json.dumps(data, ensure_ascii=False)
    if row:
        row.value = value
    else:
        s.add(Setting(key=key, value=value))


class LiveCollectionManager:
    def __init__(self, db, vault, ai, adapter_factory=None):
        self.db, self.vault, self.ai = db, vault, ai
        self.adapter_factory = adapter_factory or (
            lambda: OpenAIWebSearchVisibilityAdapter(vault)
        )
        self.executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="visibility-live"
        )

    def close(self):
        self.executor.shutdown(wait=False, cancel_futures=True)

    def key_tag(self):
        key = (self.vault.get(KEY_NAME) or {}).get("api_key")
        if not key:
            core.fail(
                "live_key_missing",
                "Chưa cấu hình OpenAI API key trong OS Credential Vault. Mở AI Settings; không gửi key vào chat.",
                409,
            )
        return hashlib.sha256(key.encode()).hexdigest()

    def state(self):
        cfg = load_settings(self.db)
        secure = True
        connected = False
        tag = None
        try:
            tag = self.key_tag()
            connected = True
        except GSCError as error:
            secure = error.code == "live_key_missing"
        with self.db.session() as s:
            row = s.get(Setting, VALIDATION_KEY)
            validation = json.loads(row.value) if row else {}
            valid = (
                validation.get("model") == cfg.model
                and validation.get("key_tag") == tag
                and connected
            )
            status = validation.get("status") if valid else "Not Validated"
            if not cfg.model:
                status = "Not Configured"
            if not connected:
                status = "Not Configured"
            pricing_ready = all(
                v is not None
                for v in (
                    cfg.input_usd_per_million,
                    cfg.output_usd_per_million,
                    cfg.tool_usd_per_thousand_calls,
                    cfg.pricing_reviewed_on,
                )
            )
            return {
                "provider": PROVIDER,
                "settings": cfg.model_dump(mode="json"),
                "key_configured": connected,
                "secure_storage_available": secure,
                "capability_status": status,
                "web_search_capability": (
                    status
                    if status
                    in (
                        "Web Search Supported",
                        "Web Search Unsupported",
                        "Permission Denied",
                        "Quota Limited",
                    )
                    else "Live Check Pending"
                ),
                "model_accessible": valid and validation.get("model_accessible", False),
                "web_search_supported": valid and status == "Web Search Supported",
                "last_validation": validation.get("checked_at") if valid else None,
                "last_response_id": validation.get("response_id") if valid else None,
                "pricing_status": (
                    "user_reviewed_estimate" if pricing_ready else "not_configured"
                ),
                "daily_used_estimate_usd": spent_today(s),
                "effective_daily_limit_usd": min(
                    cfg.daily_limit_usd, ai_settings(self.db).daily_limit_usd
                ),
                "day_timezone": "Asia/Ho_Chi_Minh",
                "live_verification": (
                    "Search Executed — Pending Human Verification"
                    if valid and status == "Web Search Supported"
                    else "Pending Live Verification"
                ),
                "api_contract_source": f"https://github.com/openai/openai-python/tree/{SDK_COMMIT}/src/openai/types/responses",
                "documentation_status": "SDK schema verified; live docs/pricing/eligibility pending",
                "siwc_used": False,
                "limitations": [
                    "GET model chỉ kiểm tra model access; không xác minh Web Search.",
                    "Không tự gọi API trả phí. Lượt kiểm tra capability cần consent riêng.",
                    "Không dùng ChatGPT SIWC hoặc chuyển sang credential khác.",
                    "Citation offsets chưa có Unicode/end convention được xác minh; hiển thị reference riêng, không highlight sai.",
                ],
            }

    def save_settings(self, data):
        with self.ai.lock, self.db.session.begin() as s:
            setting_write(s, SETTINGS_KEY, data.model_dump(mode="json"))
        return self.state()

    def validate_model(self):
        cfg = load_settings(self.db)
        if not cfg.model:
            core.fail(
                "live_model_missing", "Chọn model trước khi kiểm tra access.", 409
            )
        tag = self.key_tag()
        try:
            self.adapter_factory().validate(cfg.model)
        except GSCError as error:
            status = (
                "Quota Limited"
                if error.status == 429
                else (
                    "Permission Denied"
                    if error.code in ("ai_provider_auth", "ai_key_missing")
                    else "Not Validated"
                )
            )
            with self.db.session.begin() as s:
                setting_write(
                    s,
                    VALIDATION_KEY,
                    {
                        "model": cfg.model,
                        "key_tag": tag,
                        "model_accessible": False,
                        "status": status,
                        "checked_at": now(),
                    },
                )
            raise
        # A cheap access check must not erase an already proven matching capability.
        with self.db.session.begin() as s:
            previous = s.get(Setting, VALIDATION_KEY)
            old = json.loads(previous.value) if previous else {}
            proven = (
                old.get("key_tag") == tag
                and old.get("model") == cfg.model
                and old.get("status") == "Web Search Supported"
            )
            setting_write(
                s,
                VALIDATION_KEY,
                {
                    "model": cfg.model,
                    "key_tag": tag,
                    "model_accessible": True,
                    "status": "Web Search Supported" if proven else "Model Accessible",
                    "checked_at": now(),
                    "response_id": old.get("response_id") if proven else None,
                },
            )
        return self.state()

    def _binding(self, s, p, prompt, cfg, context, cap):
        local_project(self.db, p.local_project_id)
        return {
            "project_id": p.id,
            "local_project_id": p.local_project_id,
            "project_updated_at": p.updated_at,
            "prompt_id": prompt.id,
            "prompt_updated_at": prompt.updated_at,
            "prompt_identity": prompt.identity,
            "prompt_snapshot": prompt.text,
            "provider": PROVIDER,
            "settings": cfg.model_dump(mode="json"),
            "context": context,
            "authorized_max_usd": cap,
            "key_tag": self.key_tag(),
            "contract_version": CONTRACT_VERSION,
            "instruction_version": INSTRUCTION_VERSION,
        }

    def preflight(self, pid, data):
        cfg = load_settings(self.db)
        state = self.state()
        if not cfg.enabled or not cfg.model:
            core.fail(
                "live_disabled",
                "Bật cấu hình OpenAI Web Search và chọn model trước.",
                409,
            )
        self.key_tag()
        if not state["model_accessible"]:
            core.fail(
                "live_model_not_validated",
                "Kiểm tra model access trước. Thao tác này không chạy Web Search.",
                409,
            )
        context = {
            k: getattr(data, k) for k in ("country", "language", "city", "region")
        }
        with self.db.session.begin() as s:
            p = core.project(s, pid)
            prompt = core.scoped(s, VisibilityPrompt, data.prompt_id, pid)
            if p.status != "active" or prompt.status != "active":
                core.fail(
                    "live_inactive",
                    "Chỉ kiểm tra project và prompt đang hoạt động.",
                    409,
                )
            binding = self._binding(s, p, prompt, cfg, context, data.authorized_max_usd)
            digest = core.digest(binding)
            existing = s.scalar(
                select(CollectionRequest).where(
                    CollectionRequest.project_id == pid,
                    CollectionRequest.request_key == data.request_key,
                )
            )
            if existing:
                if existing.binding_hash != digest:
                    core.fail(
                        "live_request_key_conflict",
                        "Request key đã gắn với nội dung khác; tạo preflight mới.",
                        409,
                    )
                return self.request_view(s, existing)
            if (
                s.scalar(
                    select(func.count())
                    .select_from(CollectionRequest)
                    .where(CollectionRequest.project_id == pid)
                )
                >= 2000
            ):
                core.fail(
                    "live_request_limit",
                    "Đã đạt giới hạn 2000 collection requests/project.",
                    409,
                )
            pricing = live_costs.estimate(cfg, prompt.text, data.language)
            if data.authorized_max_usd < pricing["known_component_estimate_usd"]:
                core.fail(
                    "live_cap_below_estimate",
                    "Khoản dự phòng phải đủ cho các thành phần chi phí đã ước tính.",
                    409,
                )
            row = CollectionRequest(
                id=uid(),
                project_id=pid,
                prompt_id=prompt.id,
                request_key=data.request_key,
                status="PREFLIGHT_READY",
                active_slot=None,
                binding_hash=digest,
                snapshot={
                    "binding": binding,
                    "estimate": pricing,
                    "capability_status": state["capability_status"],
                    "expires_at": (
                        datetime.now(timezone.utc) + timedelta(minutes=10)
                    ).isoformat(),
                },
                result={},
                observation_id=None,
                usage_id=None,
                dispatched_at=None,
                created_at=now(),
                updated_at=now(),
            )
            s.add(row)
            s.flush()
            return self.request_view(s, row)

    def request_view(self, s, row):
        snapshot = {
            **row.snapshot,
            "binding": {
                k: v for k, v in row.snapshot["binding"].items() if k != "key_tag"
            },
        }
        return {
            **view(row),
            "snapshot": snapshot,
            "usage": view(s.get(AIUsage, row.usage_id)) if row.usage_id else None,
            "consent_id": s.scalar(
                select(CollectionConsent.id).where(
                    CollectionConsent.request_id == row.id
                )
            ),
            "retry_is_new_billable_request": row.status in TERMINAL,
        }

    def _check_current(self, s, row):
        cfg = load_settings(self.db)
        p = core.project(s, row.project_id)
        prompt = core.scoped(s, VisibilityPrompt, row.prompt_id, p.id)
        old = row.snapshot["binding"]
        if (
            not cfg.enabled
            or p.status != "active"
            or prompt.status != "active"
            or datetime.fromisoformat(row.snapshot["expires_at"])
            < datetime.now(timezone.utc)
        ):
            core.fail(
                "live_stale_preflight",
                "Preflight đã hết hạn/tắt hoặc prompt không hoạt động. Xem lại và tạo lượt mới.",
                409,
            )
        current = self._binding(
            s, p, prompt, cfg, old["context"], old["authorized_max_usd"]
        )
        if core.digest(current) != row.binding_hash:
            core.fail(
                "live_stale_consent",
                "Prompt/model/giá/context/credential đã đổi. Cần preflight và consent mới.",
                409,
            )
        return cfg

    def confirm(self, pid, id, data, submit=True):
        should_submit = False
        with self.ai.lock, self.db.session.begin() as s:
            row = core.scoped(s, CollectionRequest, id, pid)
            if row.status != "PREFLIGHT_READY":
                receipt = s.scalar(
                    select(CollectionConsent).where(CollectionConsent.request_id == id)
                )
                if receipt and receipt.data == data.model_dump(mode="json"):
                    return self.request_view(s, row)
                core.fail(
                    "live_already_submitted",
                    "Lượt đã được gửi/hủy; không tự chạy lại. Theo dõi request cũ.",
                    409,
                )
            cfg = self._check_current(s, row)
            if (
                data.binding_hash != row.binding_hash
                or data.authorized_max_usd
                != row.snapshot["binding"]["authorized_max_usd"]
                or not all(
                    (
                        data.acknowledge_external_processing,
                        data.confirm_exact_prompt,
                        data.acknowledge_not_billing_cap,
                    )
                )
            ):
                core.fail(
                    "live_consent_required",
                    "Cần xác nhận đúng prompt, provider, model, context, chi phí và external processing của lượt này.",
                    409,
                )
            if (
                not self.state()["web_search_supported"]
                and not data.acknowledge_capability_test
            ):
                core.fail(
                    "live_capability_consent",
                    "Web Search chưa được xác minh; cần đồng ý rõ lượt này cũng là kiểm tra capability có thể tính phí.",
                    409,
                )
            if (
                row.snapshot["estimate"]["unknown_cost_components"]
                and not data.acknowledge_uncertain_cost
            ):
                core.fail(
                    "live_uncertain_cost_consent",
                    "Cần đồng ý phần chi phí chưa xác định và khoản dự phòng nội bộ.",
                    409,
                )
            if s.scalar(
                select(CollectionRequest.id).where(CollectionRequest.active_slot == 1)
            ):
                core.fail(
                    "live_busy",
                    "Đang có một lượt trả phí khác; chờ hoàn tất trước khi xác nhận.",
                    409,
                )
            limit = min(cfg.daily_limit_usd, ai_settings(self.db).daily_limit_usd)
            if spent_today(s) + data.authorized_max_usd > limit + 1e-9:
                core.fail(
                    "live_daily_budget",
                    "Khoản dự phòng vượt ngân sách API ngày dùng chung; không gửi request.",
                    409,
                )
            receipt = CollectionConsent(
                id=uid(),
                request_id=row.id,
                binding_hash=row.binding_hash,
                data=data.model_dump(mode="json"),
                created_at=now(),
            )
            s.add(receipt)
            usage = AIUsage(
                id=uid(),
                message_id=None,
                provider="openai",
                model=cfg.model,
                request_id=None,
                status="reserved",
                input_tokens=None,
                output_tokens=None,
                reserved_usd=data.authorized_max_usd,
                estimated_cost_usd=None,
                data={
                    "operation_type": "visibility_web_search",
                    "visibility_project_id": pid,
                    "collection_request_id": row.id,
                    "pricing": cfg.model_dump(mode="json"),
                    "not_billing_cap": True,
                },
                created_at=now(),
            )
            s.add(usage)
            s.flush()
            row.usage_id = usage.id
            row.status = "QUEUED"
            row.active_slot = 1
            row.updated_at = now()
            should_submit = True
            result = self.request_view(s, row)
        if should_submit and submit:
            try:
                self.executor.submit(self.run, id)
            except RuntimeError:
                self._finish_error(
                    id,
                    "INTERRUPTED",
                    "live_executor_stopped",
                    "Chưa gửi provider; ứng dụng đang dừng.",
                    False,
                )
        return result

    def cancel(self, pid, id):
        with self.ai.lock, self.db.session.begin() as s:
            row = core.scoped(s, CollectionRequest, id, pid)
            if row.status not in ("PREFLIGHT_READY", "QUEUED") or row.dispatched_at:
                core.fail(
                    "live_cannot_cancel_dispatched",
                    "Không thể hủy chắc chắn sau khi đã gửi provider.",
                    409,
                )
            row.status = "CANCELLED_BEFORE_SUBMISSION"
            row.active_slot = None
            row.updated_at = now()
            if row.usage_id:
                usage = s.get(AIUsage, row.usage_id)
                usage.status = "cancelled_before_submission"
                usage.estimated_cost_usd = 0
            return self.request_view(s, row)

    def recover(self):
        with self.ai.lock, self.db.session.begin() as s:
            for row in s.scalars(
                select(CollectionRequest).where(
                    CollectionRequest.status.in_(["QUEUED", "RUNNING"])
                )
            ):
                row.status = (
                    "UNKNOWN_REMOTE_OUTCOME" if row.dispatched_at else "INTERRUPTED"
                )
                row.active_slot = None
                row.updated_at = now()
                row.result = {
                    **row.result,
                    "error_code": "live_interrupted",
                    "detail": "Ứng dụng khởi động lại; không tự phát lại request. Outcome/chi phí chưa xác định nếu đã dispatch.",
                }
                if row.usage_id:
                    usage = s.get(AIUsage, row.usage_id)
                    usage.status = (
                        "unknown"
                        if row.dispatched_at
                        else "interrupted_before_submission"
                    )
                    if not row.dispatched_at:
                        usage.estimated_cost_usd = 0

    def _finish_error(self, id, status, code, detail, dispatched):
        with self.ai.lock, self.db.session.begin() as s:
            row = s.get(CollectionRequest, id)
            row.status = status
            row.active_slot = None
            row.updated_at = now()
            row.result = {
                **row.result,
                "error_code": code,
                "detail": detail,
                "automatic_retry": False,
            }
            if row.usage_id:
                usage = s.get(AIUsage, row.usage_id)
                if not dispatched:
                    usage.status = "not_dispatched"
                    usage.estimated_cost_usd = 0
                elif usage.status == "reserved":
                    usage.status = "unknown"

    def run(self, id):
        dispatched = False
        provider_received = False
        tag = None
        cfg = None
        try:
            with self.ai.lock, self.db.session.begin() as s:
                row = s.get(CollectionRequest, id)
                if not row or row.status != "QUEUED":
                    return
                cfg = self._check_current(s, row)
                tag = row.snapshot["binding"]["key_tag"]
                receipt = s.scalar(
                    select(CollectionConsent).where(
                        CollectionConsent.request_id == row.id
                    )
                )
                if not receipt:
                    core.fail("live_consent_missing", "Không có consent đã lưu.", 409)
                context = row.snapshot["binding"]["context"]
                prompt = row.snapshot["binding"]["prompt_snapshot"]
                prompt_id = row.prompt_id
                receipt_id = receipt.id
                row.status = "RUNNING"
                row.dispatched_at = now()
                row.updated_at = now()
            dispatched = True
            envelope = self.adapter_factory().observe(
                prompt_snapshot=prompt,
                consent_receipt_id=receipt_id,
                settings=cfg,
                context=context,
                prompt_id=prompt_id,
                collection_request_id=id,
                credential_tag=tag,
            )
            raw = envelope["raw_response"]
            parsed = envelope["parsed"]
            provider_received = True
            safe = (
                redact(raw) == raw
                and len(json.dumps(raw, ensure_ascii=False).encode()) <= 256 * 1024
            )
            with self.db.session.begin() as s:
                row = s.get(CollectionRequest, id)
                usage = s.get(AIUsage, row.usage_id)
                if parsed:
                    costs = live_costs.after(
                        cfg,
                        parsed["usage"],
                        parsed["web_search_call_count"],
                        parsed["actual_model"],
                    )
                    usage.request_id = parsed["response_id"]
                    usage.input_tokens = costs["input_tokens"]
                    usage.output_tokens = costs["output_tokens"]
                    usage.estimated_cost_usd = costs["estimated_total_usd"]
                    usage.status = (
                        "completed_estimate"
                        if costs["estimated_total_usd"] is not None
                        else "unknown"
                    )
                    usage.data = {**usage.data, **costs, "actions": parsed["actions"]}
                    row.result = {
                        k: v
                        for k, v in parsed.items()
                        if k not in ("candidate", "sources", "answer_citations")
                    }
                    row.result["costs"] = costs
                else:
                    # Parser/metadata failures do not erase token counts actually
                    # returned by the provider. Dollar total stays unknown.
                    tokens = (
                        raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
                    )
                    a, b = tokens.get("input_tokens"), tokens.get("output_tokens")
                    usage.input_tokens = (
                        a if type(a) is int and 0 <= a <= 1_000_000_000 else None
                    )
                    usage.output_tokens = (
                        b if type(b) is int and 0 <= b <= 1_000_000_000 else None
                    )
                    usage.status = "unknown"
                    usage.data = {
                        **usage.data,
                        "unknown_cost_components": ["provider_normalization_failed"],
                        "provider_reported_dollar_cost": None,
                    }
                row.result = {
                    **row.result,
                    "provider_response": raw if safe else None,
                    "provider_response_retained": safe,
                }
            if not parsed or not safe:
                self._finish_error(
                    id,
                    "FAILED",
                    "live_normalization_failed",
                    "Payload không hợp lệ/quá lớn/nhạy cảm; không tạo observation thành công. Chi phí có thể chưa xác định.",
                    True,
                )
                return
            # Usage/raw diagnostic is committed before ingestion, so a DB/validation
            # failure cannot turn a billed call into an invisible request.
            with self.db.session.begin() as s:
                row = s.get(CollectionRequest, id)
                p = core.project(s, row.project_id)
                if parsed["candidate"]:
                    observation, _ = core.ingest(s, p, parsed["candidate"])
                    row.observation_id = observation.id
                for source in parsed["sources"]:
                    s.add(
                        SearchSource(
                            id=uid(),
                            request_id=id,
                            project_id=p.id,
                            observation_id=row.observation_id,
                            normalized_url=source["normalized_url"],
                            data=source,
                        )
                    )
                row.status = parsed["status"]
                row.active_slot = None
                row.updated_at = now()
                if parsed["eligible"]:
                    setting_write(
                        s,
                        VALIDATION_KEY,
                        {
                            "model": cfg.model,
                            "key_tag": tag,
                            "model_accessible": True,
                            "status": "Web Search Supported",
                            "checked_at": now(),
                            "response_id": parsed["response_id"],
                        },
                    )
            # No automatic GEO detection, Agent inference or website action follows.
        except LiveProviderError as error:
            self._finish_error(
                id,
                "UNKNOWN_REMOTE_OUTCOME" if error.uncertain else "FAILED",
                error.code,
                error.message,
                dispatched and error.submitted,
            )
            if cfg and tag and error.capability:
                with self.db.session.begin() as s:
                    setting_write(
                        s,
                        VALIDATION_KEY,
                        {
                            "model": cfg.model,
                            "key_tag": tag,
                            "model_accessible": True,
                            "status": error.capability,
                            "checked_at": now(),
                        },
                    )
        except GSCError as error:
            self._finish_error(
                id,
                "FAILED",
                error.code,
                "Không thể hoàn thành collection. Xem cấu hình/request đã lưu; không tự retry.",
                dispatched,
            )
        except Exception:
            self._finish_error(
                id,
                (
                    "FAILED"
                    if not dispatched or provider_received
                    else "UNKNOWN_REMOTE_OUTCOME"
                ),
                "live_ingestion_failed" if provider_received else "live_local_failure",
                "Lỗi xử lý/lưu dữ liệu; giữ request và usage. Không tự phát lại API.",
                dispatched,
            )
