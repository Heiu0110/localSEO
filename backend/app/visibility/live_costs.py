"""Explicit estimates, never provider dollar billing or a guaranteed monetary cap."""

from decimal import Decimal
from . import core


def estimate(cfg, prompt, language):
    prices = (
        cfg.input_usd_per_million,
        cfg.output_usd_per_million,
        cfg.tool_usd_per_thousand_calls,
    )
    if any(v is None for v in prices) or not cfg.pricing_reviewed_on:
        core.fail(
            "live_pricing_missing",
            "Cần đủ giá input/output/search tool và ngày kiểm tra giá. Không lấy model-token cost làm tổng Web Search.",
            409,
        )
    # An assumption, not a token/billing cap: search content may expand beyond it.
    input_tokens = (
        len(prompt.encode())
        + 1024
        + cfg.search_content_tokens_per_call * cfg.max_tool_calls
    )
    model = float(
        (
            Decimal(input_tokens) * Decimal(str(prices[0]))
            + Decimal(cfg.max_output_tokens) * Decimal(str(prices[1]))
        )
        / Decimal(1000000)
    )
    tool = float(Decimal(cfg.max_tool_calls) * Decimal(str(prices[2])) / Decimal(1000))
    unknown = (
        ["search_content_billing_unverified"]
        if cfg.search_content_billing == "unverified"
        else []
    )
    return {
        "currency": "USD",
        "estimated_input_tokens": input_tokens,
        "max_output_tokens": cfg.max_output_tokens,
        "estimated_search_calls": cfg.max_tool_calls,
        "model_estimate_usd": round(model, 8),
        "tool_estimate_usd": round(tool, 8),
        "known_component_estimate_usd": round(model + tool, 8),
        "total_estimate_usd": round(model + tool, 8) if not unknown else None,
        "unknown_cost_components": unknown,
        "pricing": cfg.model_dump(mode="json"),
        "pricing_status": "user_reviewed_estimate_not_provider_verified",
        "not_billing_cap": True,
        "limitations": [
            "Giá là cấu hình người dùng; chưa xác minh trang giá live trong môi trường phát triển.",
            "Token search context là giả định; max_tool_calls/max_output_tokens không giới hạn USD của OpenAI.",
            "Khoản dự phòng do ứng dụng kiểm soát, không phải provider-side billing cap.",
        ],
    }


def after(cfg, usage, call_count, actual_model):
    a, b = usage.get("input_tokens"), usage.get("output_tokens")
    # Bound untrusted counters before Decimal/float/SQLite conversion. Values
    # beyond this diagnostic ceiling remain in raw response, not dollar math.
    known = all(type(value) is int and 0 <= value <= 1_000_000_000 for value in (a, b))
    unknown = []
    if not known:
        unknown.append("token_usage_missing_or_invalid")
    if cfg.search_content_billing == "unverified":
        unknown.append("search_content_billing_unverified")
    if actual_model != cfg.model:
        unknown.append("actual_model_pricing_not_independently_verified")
    model = None
    if known:
        extra = (
            cfg.search_content_tokens_per_call * call_count
            if cfg.search_content_billing == "additional_estimate"
            else 0
        )
        model = float(
            (
                Decimal(a + extra) * Decimal(str(cfg.input_usd_per_million))
                + Decimal(b) * Decimal(str(cfg.output_usd_per_million))
            )
            / Decimal(1000000)
        )
    tool = float(
        Decimal(call_count)
        * Decimal(str(cfg.tool_usd_per_thousand_calls))
        / Decimal(1000)
    )
    return {
        "input_tokens": a if known else None,
        "output_tokens": b if known else None,
        "web_search_call_count": call_count,
        "estimated_model_cost_usd": round(model, 8) if model is not None else None,
        "estimated_tool_cost_usd": round(tool, 8),
        "estimated_total_usd": (
            round(model + tool, 8) if model is not None and not unknown else None
        ),
        "unknown_cost_components": unknown,
        "provider_reported_dollar_cost": None,
        "pricing_status": "user_estimate",
        "not_billing_cap": True,
    }
