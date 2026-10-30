"""Responses API parser. Search actions, SEARCH_SOURCE and ANSWER_CITATION stay separate."""

import ipaddress
import socket
import json
import re
from urllib.parse import urlsplit
from .extraction import normalize_url
from .schemas import CitationInput, ObservationInput
from .live_schemas import CONTRACT_VERSION, INSTRUCTION_VERSION
from app.ai.common import now, redact

MAX_RESPONSE_BYTES = 256 * 1024


def public_url(value):
    value = normalize_url(value)
    host = urlsplit(value).hostname
    if host in ("localhost", "metadata.google.internal") or host.endswith(
        (".localhost", ".local", ".internal")
    ):
        raise ValueError("Private URL")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        try:
            # inet_aton parses numeric legacy IPv4 forms locally; it performs no
            # DNS lookup. Browsers can treat 127.1 / 0x7f000001 as loopback.
            address = ipaddress.IPv4Address(socket.inet_aton(host))
        except (OSError, OverflowError):
            address = None
    if address and not address.is_global:
        raise ValueError("Private URL")
    return value


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid(_):
        raise ValueError("Non-finite JSON number")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    # Reject lone surrogates before persisting or rendering a provider payload.
    json.dumps(value, ensure_ascii=False).encode("utf-8")
    return value


def span_mapping(text, start, end):
    # Official SDK says character indices but does not specify Unicode unit or
    # inclusive/exclusive convention. Never assert a mapping based on a guess.
    valid = (
        type(start) is int
        and type(end) is int
        and 0 <= start < end <= len(text.encode("utf-16-le")) // 2
    )
    return {
        "status": (
            "unavailable_contract_unit_unverified" if valid else "invalid_offsets"
        ),
        "start": start,
        "end": end,
        "offset_unit": "unknown",
        "highlight_verified": False,
    }


def parse_response(
    raw,
    request_id,
    prompt_id,
    prompt_snapshot,
    context,
    requested_model,
    tool_configuration=None,
):
    problems, notes, sources, citations, native, actions, segments = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    if not isinstance(raw, dict) or redact(raw) != raw:
        raise ValueError("Provider response invalid or contains sensitive values")
    if not isinstance(raw.get("id"), str) or not re.fullmatch(
        r"resp_[A-Za-z0-9_-]{1,150}", raw["id"]
    ):
        raise ValueError("Provider response ID missing")
    if not isinstance(raw.get("model"), str) or len(raw["model"]) > 160:
        raise ValueError("Actual provider model missing")
    output = raw.get("output")
    if not isinstance(output, list) or len(output) > 100:
        raise ValueError("Provider output invalid or exceeds limit")
    answer = ""
    refusal = False
    citation_complete = True
    message_complete = True
    seen_cites = set()
    seen_sources = set()
    search_calls = []
    for item_index, item in enumerate(output):
        if not isinstance(item, dict):
            problems.append("invalid_output_item")
            message_complete = False
            continue
        kind = item.get("type")
        if kind == "web_search_call":
            search_calls.append(item)
            action = item.get("action")
            if (
                not isinstance(action, dict)
                or action.get("type") not in ("search", "open_page", "find_in_page")
                or item.get("status")
                not in ("completed", "in_progress", "searching", "failed", "incomplete")
                or not isinstance(item.get("id"), str)
            ):
                problems.append("invalid_search_call")
                continue
            actions.append(
                {"call_id": item["id"], "status": item["status"], "action": action}
            )
            if action.get("type") == "search":
                rows = action.get("sources")
                if rows is None:
                    notes.append("optional_search_sources_unavailable")
                    continue
                if not isinstance(rows, list) or len(rows) > 200:
                    problems.append("invalid_or_oversized_search_sources")
                    continue
                for source in rows:
                    try:
                        if not isinstance(source, dict) or source.get("type") != "url":
                            raise ValueError()
                        url = public_url(source.get("url"))
                        signature = (item["id"], url)
                        if signature in seen_sources:
                            continue
                        seen_sources.add(signature)
                        sources.append(
                            {
                                "type": "SEARCH_SOURCE",
                                "normalized_url": url,
                                "call_id": item["id"],
                                "original": source,
                                "source_content_verified": False,
                            }
                        )
                    except (ValueError, TypeError, AttributeError):
                        notes.append("invalid_search_source_url_omitted")
        elif kind == "message":
            if item.get("role") != "assistant" or item.get("status") != "completed":
                message_complete = False
            content = item.get("content")
            if not isinstance(content, list) or len(content) > 100:
                problems.append("invalid_message_content")
                message_complete = False
                continue
            for content_index, block in enumerate(content):
                if not isinstance(block, dict):
                    problems.append("invalid_content_block")
                    message_complete = False
                    continue
                if block.get("type") == "refusal":
                    refusal = True
                    notes.append("provider_refusal")
                    continue
                if block.get("type") != "output_text":
                    problems.append("unsupported_content_type")
                    message_complete = False
                    continue
                text = block.get("text")
                if not isinstance(text, str):
                    problems.append("output_text_missing")
                    message_complete = False
                    continue
                base = len(answer)
                answer += text
                segments.append(
                    {
                        "response_item_id": item.get("id"),
                        "content_index": content_index,
                        "start_codepoint": base,
                        "end_codepoint": len(answer),
                    }
                )
                annotations = block.get("annotations")
                if not isinstance(annotations, list) or len(annotations) > 100:
                    citation_complete = False
                    problems.append("annotation_collection_missing_or_invalid")
                    continue
                for order, annotation in enumerate(annotations):
                    annotation_id = f"{item_index}:{content_index}:{order}"
                    record = {
                        "type": "ANSWER_CITATION",
                        "annotation_id": annotation_id,
                        "response_item_id": item.get("id"),
                        "content_index": content_index,
                        "order": order + 1,
                        "provider": "openai",
                        "provider_response_id": raw["id"],
                        "original_annotation": annotation,
                    }
                    native.append(record)
                    try:
                        if (
                            not isinstance(annotation, dict)
                            or annotation.get("type") != "url_citation"
                        ):
                            raise ValueError()
                        url = public_url(annotation.get("url"))
                        title = annotation.get("title")
                        if not isinstance(title, str) or len(title) > 2000:
                            raise ValueError()
                        start, end = annotation.get("start_index"), annotation.get(
                            "end_index"
                        )
                        mapping = span_mapping(text, start, end)
                        record.update(
                            normalized_url=url,
                            title=title,
                            span_mapping=mapping,
                            source_content_verified=False,
                        )
                        if mapping["status"] == "invalid_offsets":
                            citation_complete = False
                            problems.append("invalid_citation_offsets")
                        signature = (item_index, content_index, url, title, start, end)
                        if signature in seen_cites:
                            record["duplicate_of_existing"] = True
                            continue
                        seen_cites.add(signature)
                        # URL attribution can be structurally validated even when the
                        # exact text-span convention has not been verified live.
                        citations.append(
                            CitationInput(
                                url=url,
                                source_type="provider_annotation",
                                annotation_id=annotation_id,
                                offset_unit="unknown",
                                source_verification="provider_reported",
                            ).model_dump(mode="json")
                        )
                    except (ValueError, TypeError, AttributeError):
                        citation_complete = False
                        problems.append("malformed_native_citation")
        elif kind == "reasoning":
            pass
        else:
            problems.append("unsupported_output_item")
            message_complete = False
    if (
        len(sources) > 200
        or len(citations) > 100
        or len(native) > 100
        or len(answer) > 30000
    ):
        raise ValueError("Normalized result exceeds storage limits")
    searches = [a for a in actions if a["action"]["type"] == "search"]
    if not search_calls:
        execution = "NO_SEARCH_EXECUTED"
    elif not actions or "invalid_search_call" in problems:
        execution = "SEARCH_EXECUTION_UNKNOWN"
    elif any(a["status"] in ("failed", "incomplete") for a in actions):
        execution = "SEARCH_FAILED"
    elif not searches:
        execution = "NO_SEARCH_EXECUTED"
    elif any(a["status"] != "completed" for a in actions):
        execution = "SEARCH_EXECUTED"
    else:
        execution = "SEARCH_COMPLETED"
    response_complete = (
        raw.get("status") == "completed"
        and message_complete
        and bool(answer.strip())
        and not refusal
    )
    eligible = response_complete and execution == "SEARCH_COMPLETED"
    if not response_complete:
        problems.append("response_incomplete_or_refused")
    if not eligible:
        notes.append("excluded_from_completed_grounded_cohort")
    if not answer.strip():
        candidate = None
    else:
        meta = {
            "collection_request_id": request_id,
            "provider_response_id": raw["id"],
            "provider_status": raw.get("status"),
            "actual_model": raw["model"],
            "requested_model": requested_model,
            "search_execution": execution,
            "search_actions": actions,
            "search_sources_reference": f"/api/visibility/collection/requests/{request_id}/sources",
            "answer_citations": native,
            "text_segments": segments,
            "requested_context": context,
            "applied_location": None,
            "device": None,
            "locale_note": "Requested approximate location/language, not verified physical search location or observed answer language.",
            "tool_configuration": tool_configuration,
            "measurement_profile": (
                f"web_search/{tool_configuration.get('search_context_size','unknown')}/calls{tool_configuration.get('max_tool_calls','unknown')}/out{tool_configuration.get('max_output_tokens','unknown')}/{INSTRUCTION_VERSION}"
                if tool_configuration
                else None
            ),
            "measurement_instruction_version": INSTRUCTION_VERSION,
            "provider_contract_version": CONTRACT_VERSION,
            "citation_span_contract": "unknown; separate references only",
            "normalization_notes": list(dict.fromkeys(notes + problems)),
        }
        candidate = ObservationInput(
            prompt_id=prompt_id,
            provider="openai_web_search",
            model=raw["model"],
            collection_method="PROVIDER_API",
            prompt_snapshot=prompt_snapshot,
            response_text=answer,
            grounding="enabled" if execution == "SEARCH_COMPLETED" else "unknown",
            country=context.get("country"),
            language=context.get("language"),
            location=", ".join(
                x for x in (context.get("city"), context.get("region")) if x
            )
            or None,
            observed_at=now(),
            citation_capability=(
                "capable" if execution == "SEARCH_COMPLETED" else "unknown"
            ),
            citation_metadata=(
                "complete"
                if eligible and citation_complete
                else "partial" if execution == "SEARCH_COMPLETED" else "missing"
            ),
            completeness="complete" if eligible else "partial",
            citations=citations,
            source_metadata=meta,
        )
    return {
        "candidate": candidate,
        "search_execution": execution,
        "actions": actions,
        "sources": sources,
        "answer_citations": native,
        "citation_count": len(citations),
        "source_count": len(sources),
        "response_id": raw["id"],
        "actual_model": raw["model"],
        "provider_status": raw.get("status"),
        "usage": raw.get("usage") if isinstance(raw.get("usage"), dict) else {},
        "web_search_call_count": len(search_calls),
        "problems": list(dict.fromkeys(problems)),
        "notes": list(dict.fromkeys(notes)),
        "eligible": eligible,
        "status": (
            "COMPLETED"
            if eligible and citation_complete and not problems
            else "PARTIAL"
        ),
    }
