"""Provider-shaped fixtures and one-shot financial safety; no live paid calls."""

import copy
from unittest.mock import Mock
from pathlib import Path
import json
from datetime import datetime, timezone
import httpx
import pytest
from sqlalchemy import select, func
from test_ai import env
from test_visibility import visibility
from app.ai.models import AIUsage
from app.ai.provider import KEY_NAME
from app.gsc.errors import GSCError
from app.visibility.live_models import CollectionRequest
from app.visibility.live_schemas import (
    LiveSettings,
    CollectionPreflight,
    CollectionConfirmation,
)
from app.visibility.live_parser import parse_response, strict_json, public_url
from app.visibility.openai_web_search import OpenAIWebSearchVisibilityAdapter


def native_response(text="Acme Balo và Beta Bags có thể được nhắc.", citations=None):
    if citations is None:
        citations = [
            {
                "type": "url_citation",
                "url": "https://acme.test/source",
                "title": "Acme official source",
                "start_index": 0,
                "end_index": 9,
            }
        ]
    return {
        "id": "resp_fixture_001",
        "status": "completed",
        "model": "fixture-model",
        "output": [
            {"type": "reasoning", "id": "rs_fixture", "summary": []},
            {
                "id": "ws_fixture",
                "type": "web_search_call",
                "status": "completed",
                "action": {
                    "type": "search",
                    "queries": ["xưởng may balo"],
                    "sources": [
                        {"type": "url", "url": "https://beta.test/retrieved-not-cited"},
                        {"type": "url", "url": "https://acme.test/source"},
                    ],
                },
            },
            {
                "type": "message",
                "id": "msg_fixture",
                "status": "completed",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": text, "annotations": citations}
                ],
            },
        ],
        "usage": {"input_tokens": 350, "output_tokens": 120, "total_tokens": 470},
    }


@pytest.fixture
def live(visibility):
    c, r, pid, brand, competitor, prompt, write = visibility
    r.oauth.vault.put(KEY_NAME, {"api_key": "sk-fixture-not-a-real-key-000000"})
    cfg = LiveSettings(
        enabled=True,
        model="fixture-model",
        input_usd_per_million=1,
        output_usd_per_million=2,
        tool_usd_per_thousand_calls=10,
        pricing_reviewed_on=datetime.now(timezone.utc).date(),
        search_content_billing="reported_input",
    )
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200,
            json=(
                {"id": "fixture-model"}
                if request.method == "GET"
                else native_response()
            ),
        )

    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault, transport=httpx.MockTransport(handler)
    )
    r.visibility_live.save_settings(cfg)
    r.visibility_live.validate_model()
    yield (*visibility, cfg, calls)
    r.visibility_live.close()


def preflight(live, key="fixture-request-0001"):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    return r.visibility_live.preflight(
        pid,
        CollectionPreflight(
            prompt_id=prompt["id"],
            request_key=key,
            country="VN",
            language="vi",
            authorized_max_usd=0.1,
        ),
    )


def confirmation(request):
    return CollectionConfirmation(
        binding_hash=request["binding_hash"],
        authorized_max_usd=0.1,
        acknowledge_external_processing=True,
        confirm_exact_prompt=True,
        acknowledge_not_billing_cap=True,
        acknowledge_capability_test=True,
        acknowledge_uncertain_cost=True,
    )


def finish(live, request=None):
    c, r, pid, *_ = live
    request = request or preflight(live)
    r.visibility_live.confirm(pid, request["id"], confirmation(request), submit=False)
    r.visibility_live.run(request["id"])
    response = c.get(
        f"/api/visibility/collection/requests/{request['id']}?project_id={pid}"
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_full_pipeline_financial_ledger_and_geo(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    assert len(calls) == 1 and calls[0].method == "GET"
    assert "key_tag" not in pending["snapshot"]["binding"]
    result = finish(live, pending)
    assert result["status"] == "COMPLETED", result
    payload = json.loads(calls[-1].content)
    assert len(calls) == 2 and payload["input"][0]["content"] == prompt["text"]
    assert "Acme" not in json.dumps(payload) and payload["tool_choice"] == "required"
    assert payload["store"] is False and payload["max_tool_calls"] == 1
    assert payload["tools"][0]["type"] == "web_search" and payload["tools"][0][
        "user_location"
    ] == {"type": "approximate", "country": "VN"}
    row = c.get(
        f"/api/visibility/observations/{result['observation_id']}?project_id={pid}"
    ).json()
    assert row["response_text"] == native_response()["output"][2]["content"][0]["text"]
    assert row["collection_method"] == "PROVIDER_API" and len(row["citations"]) == 1
    assert (
        row["citations"][0]["entity_id"] == brand["id"]
        and row["citations"][0]["data"]["start"] is None
    )
    sources = c.get(
        f"/api/visibility/observations/{row['id']}/search-sources?project_id={pid}"
    ).json()
    assert len(sources) == 2 and all(
        x["data"]["type"] == "SEARCH_SOURCE" for x in sources
    )
    group = c.get(f"/api/visibility/overview?project_id={pid}").json()["groups"][0]
    assert group["brand_citation_rate"] == {
        "numerator": 1,
        "denominator": 1,
        "percent": 100,
    }
    assert (
        "GEO-CITE-001" not in write("opportunities/detect", {})["data"]["rules_applied"]
    )
    assert r.visibility_live.state()["web_search_supported"] is True
    with r.db.session() as s:
        assert s.scalar(select(func.count()).select_from(AIUsage)) == 1
        assert s.get(AIUsage, result["usage_id"]).estimated_cost_usd == pytest.approx(
            0.01059
        )
    r.visibility_live.confirm(pid, pending["id"], confirmation(pending), submit=False)
    r.visibility_live.run(pending["id"])
    assert len(calls) == 2


@pytest.mark.parametrize(
    "mutation,execution,eligible,metadata",
    [
        ("zero", "SEARCH_COMPLETED", True, "complete"),
        ("missing_annotations", "SEARCH_COMPLETED", True, "partial"),
        ("no_search", "NO_SEARCH_EXECUTED", False, "missing"),
        ("open_only", "NO_SEARCH_EXECUTED", False, "missing"),
        ("search_failed", "SEARCH_FAILED", False, "missing"),
        ("search_running", "SEARCH_EXECUTED", False, "missing"),
        ("incomplete", "SEARCH_COMPLETED", False, "partial"),
        ("refusal", "SEARCH_COMPLETED", False, None),
        ("bad_offsets", "SEARCH_COMPLETED", True, "partial"),
        ("bad_url", "SEARCH_COMPLETED", True, "partial"),
        ("source_missing", "SEARCH_COMPLETED", True, "complete"),
    ],
)
def test_execution_and_citation_completeness(mutation, execution, eligible, metadata):
    raw = native_response()
    block = raw["output"][2]["content"][0]
    if mutation == "zero":
        block["annotations"] = []
    elif mutation == "missing_annotations":
        del block["annotations"]
    elif mutation == "no_search":
        raw["output"].pop(1)
    elif mutation == "open_only":
        raw["output"][1]["action"] = {"type": "open_page", "url": "https://example.com"}
    elif mutation == "search_failed":
        raw["output"][1]["status"] = "failed"
    elif mutation == "search_running":
        raw["output"][1]["status"] = "searching"
    elif mutation == "incomplete":
        raw["status"] = "incomplete"
    elif mutation == "refusal":
        raw["output"][2]["content"] = [{"type": "refusal", "refusal": "Cannot answer"}]
    elif mutation == "bad_offsets":
        block["annotations"][0]["end_index"] = 99999
    elif mutation == "bad_url":
        block["annotations"][0]["url"] = "javascript:alert(1)"
    elif mutation == "source_missing":
        del raw["output"][1]["action"]["sources"]
    parsed = parse_response(
        raw, "request", "prompt", "Neutral question", {}, "fixture-model"
    )
    assert parsed["search_execution"] == execution and parsed["eligible"] is eligible
    if metadata:
        assert parsed["candidate"].citation_metadata == metadata
    else:
        assert parsed["candidate"] is None
    if mutation == "zero":
        assert parsed["citation_count"] == 0
    if mutation == "source_missing":
        assert parsed["citation_count"] == 1 and parsed["source_count"] == 0


def test_unicode_multiple_messages_and_duplicate_annotations():
    raw = native_response("😀 Acme Balo — tiếng Việt 𠀀.")
    block = raw["output"][2]["content"][0]
    original = copy.deepcopy(block["annotations"][0])
    block["annotations"] = [original, copy.deepcopy(original)]
    another = copy.deepcopy(raw["output"][2])
    another["id"] = "msg_two"
    another["content"][0]["text"] = "\nBeta Bags."
    another["content"][0]["annotations"] = [
        {
            "type": "url_citation",
            "url": "https://beta.test/a",
            "title": "Beta source",
            "start_index": 1,
            "end_index": 5,
        }
    ]
    raw["output"] = [another, *raw["output"]]
    parsed = parse_response(raw, "request", "prompt", "Question", {}, "fixture-model")
    assert parsed["citation_count"] == 2 and len(parsed["answer_citations"]) == 3
    assert (
        parsed["candidate"].response_text == "\nBeta Bags.😀 Acme Balo — tiếng Việt 𠀀."
    )
    assert parsed["answer_citations"][1]["original_annotation"] == original
    assert all(
        c.start is None and c.offset_unit == "unknown"
        for c in parsed["candidate"].citations
    )


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_http_errors_never_retry_or_fallback(live, status):
    c, r, pid, *_ = live
    paid = []

    def bad(request):
        paid.append(request)
        return httpx.Response(
            status, json={"error": {"message": "secret upstream text"}}
        )

    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault, transport=httpx.MockTransport(bad)
    )
    result = finish(live)
    assert len(paid) == 1 and result["status"] == (
        "UNKNOWN_REMOTE_OUTCOME" if status == 500 else "FAILED"
    )
    assert (
        not result["observation_id"] and result["usage"]["estimated_cost_usd"] is None
    )
    assert "secret upstream text" not in json.dumps(result)


@pytest.mark.parametrize(
    "failure", ["timeout", "reset", "oversized", "bad_json", "invalid_object"]
)
def test_unknown_outcomes_keep_reservation(live, failure):
    c, r, pid, *_ = live
    paid = []

    def bad(request):
        paid.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private detail")
        if failure == "reset":
            raise httpx.ReadError("private detail")
        if failure == "oversized":
            return httpx.Response(200, content=b"x" * (256 * 1024 + 1))
        if failure == "bad_json":
            return httpx.Response(200, content=b"{broken")
        return httpx.Response(200, json=[])

    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault, transport=httpx.MockTransport(bad)
    )
    result = finish(live)
    assert len(paid) == 1 and result["status"] == "UNKNOWN_REMOTE_OUTCOME"
    assert (
        result["usage"]["reserved_usd"] == 0.1
        and result["usage"]["estimated_cost_usd"] is None
    )
    assert "private detail" not in json.dumps(result)


def test_stale_consent_single_active_and_restart_recovery(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    bad = confirmation(pending).model_copy(
        update={"acknowledge_external_processing": False}
    )
    with pytest.raises(GSCError):
        r.visibility_live.confirm(pid, pending["id"], bad, submit=False)
    r.visibility_live.save_settings(cfg.model_copy(update={"max_output_tokens": 1600}))
    with pytest.raises(GSCError) as error:
        r.visibility_live.confirm(
            pid, pending["id"], confirmation(pending), submit=False
        )
    assert error.value.code == "live_stale_consent"
    r.visibility_live.save_settings(cfg)
    r.visibility_live.confirm(pid, pending["id"], confirmation(pending), submit=False)
    another = preflight(live, "fixture-request-other")
    with pytest.raises(GSCError) as error:
        r.visibility_live.confirm(
            pid, another["id"], confirmation(another), submit=False
        )
    assert error.value.code == "live_busy"
    r.visibility_live.recover()
    with r.db.session() as s:
        assert s.get(CollectionRequest, pending["id"]).status == "INTERRUPTED"
        assert (
            s.get(
                AIUsage, s.get(CollectionRequest, pending["id"]).usage_id
            ).estimated_cost_usd
            == 0
        )
    r.visibility_live.confirm(pid, another["id"], confirmation(another), submit=False)
    with r.db.session.begin() as s:
        row = s.get(CollectionRequest, another["id"])
        row.status = "RUNNING"
        row.dispatched_at = datetime.now(timezone.utc).isoformat()
    r.visibility_live.recover()
    r.visibility_live.run(another["id"])
    with r.db.session() as s:
        assert (
            s.get(CollectionRequest, another["id"]).status == "UNKNOWN_REMOTE_OUTCOME"
        )
    assert len(calls) == 1


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "http://127.0.0.1/a",
        "http://2130706433/a",
        "http://0x7f000001/a",
        "http://127.1/a",
        "http://0177.0.0.1/a",
        "http://[::1]/a",
        "http://169.254.169.254/a",
        "https://localhost/a",
        "https://u:p@example.com/a",
    ],
)
def test_private_or_unsafe_citation_urls(url):
    with pytest.raises((ValueError, TypeError)):
        public_url(url)


@pytest.mark.parametrize("raw", ['{"x":1,"x":2}', '{"x":NaN}', "[]"])
def test_strict_provider_json(raw):
    with pytest.raises(ValueError):
        strict_json(raw)


@pytest.mark.parametrize(
    "component",
    [
        "input_usd_per_million",
        "output_usd_per_million",
        "tool_usd_per_thousand_calls",
        "pricing_reviewed_on",
    ],
)
def test_missing_price_component_never_becomes_free(live, component):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    r.visibility_live.save_settings(cfg.model_copy(update={component: None}))
    with pytest.raises(GSCError) as error:
        preflight(live)
    assert error.value.code == "live_pricing_missing" and len(calls) == 1


def test_shared_daily_budget_and_key_rotation(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    r.oauth.vault.put(KEY_NAME, {"api_key": "sk-fixture-rotated-key-000000"})
    with pytest.raises(GSCError) as error:
        r.visibility_live.confirm(
            pid, pending["id"], confirmation(pending), submit=False
        )
    assert error.value.code == "live_stale_consent"
    r.visibility_live.validate_model()
    pending = preflight(live, "fixture-key-rotation-02")
    with r.db.session.begin() as s:
        s.add(
            AIUsage(
                id="existing-agent-cost",
                message_id=None,
                provider="openai",
                model="fixture-model",
                request_id="old-agent",
                status="unknown",
                input_tokens=None,
                output_tokens=None,
                reserved_usd=0.95,
                estimated_cost_usd=None,
                data={"operation_type": "agent"},
                created_at=datetime.now(timezone.utc).isoformat(),
            )
        )
    with pytest.raises(GSCError) as error:
        r.visibility_live.confirm(
            pid, pending["id"], confirmation(pending), submit=False
        )
    assert error.value.code == "live_daily_budget" and all(
        call.method == "GET" for call in calls
    )


def test_idempotent_preflight_expired_confirmation_and_cancellation(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    assert preflight(live)["id"] == pending["id"]
    with r.db.session.begin() as s:
        row = s.get(CollectionRequest, pending["id"])
        row.snapshot = {**row.snapshot, "expires_at": "2000-01-01T00:00:00+00:00"}
    with pytest.raises(GSCError):
        r.visibility_live.confirm(
            pid, pending["id"], confirmation(pending), submit=False
        )
    other = preflight(live, "fixture-cancel-before-submit")
    r.visibility_live.confirm(pid, other["id"], confirmation(other), submit=False)
    assert (
        r.visibility_live.cancel(pid, other["id"])["status"]
        == "CANCELLED_BEFORE_SUBMISSION"
    )
    r.visibility_live.run(other["id"])
    assert len(calls) == 1


def test_project_scope_csrf_and_credential_boundary(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    other = c.post(
        "/api/visibility/projects",
        json={"local_project_id": "xuong-may", "name": "Other project"},
    ).json()["id"]
    assert (
        c.get(
            f"/api/visibility/collection/requests/{pending['id']}?project_id={other}"
        ).status_code
        == 403
    )
    assert (
        c.get(
            f"/api/visibility/collection/requests/{pending['id']}/sources?project_id={other}"
        ).status_code
        == 403
    )
    assert (
        c.post(
            f"/api/visibility/collection/requests/{pending['id']}/confirm?project_id={other}",
            json=confirmation(pending).model_dump(),
        ).status_code
        == 403
    )
    c.headers.pop("X-CSRF-Token", None)
    assert (
        c.post(
            "/api/visibility/providers/openai-web-search/validate-model", json={}
        ).status_code
        == 403
    )
    assert "sk-fixture" not in json.dumps(pending) and "sk-fixture" not in json.dumps(
        r.visibility_live.state()
    )
    r.oauth.vault.delete(KEY_NAME)
    assert r.visibility_live.state()["key_configured"] is False
    with pytest.raises(GSCError) as error:
        preflight(live, "fixture-without-key-01")
    assert error.value.code == "live_key_missing"
    assert len(calls) == 1


@pytest.mark.parametrize("kind", ["no_search", "zero", "missing", "competitor"])
def test_full_ingestion_denominators_and_geo_use_native_answer_citations(live, kind):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    raw = native_response()
    if kind == "no_search":
        raw["output"].pop(1)
    elif kind == "zero":
        raw["output"][2]["content"][0]["annotations"] = []
    elif kind == "missing":
        del raw["output"][2]["content"][0]["annotations"]
    else:
        raw["output"][2]["content"][0]["text"] = "Beta Bags được nhắc."
        raw["output"][2]["content"][0]["annotations"][0].update(
            url="https://beta.test/a", title="Beta source"
        )
    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
    )
    result = finish(live)
    report = c.get(f"/api/visibility/overview?project_id={pid}").json()
    detection = write("opportunities/detect", {})
    rules = detection["data"]["rules_applied"]
    if kind == "no_search":
        assert (
            result["status"] == "PARTIAL"
            and report["eligible_observations"] == 0
            and not rules
        )
        diagnostic_scope = c.get(
            f"/api/visibility/overview?project_id={pid}&require_complete=false"
        ).json()
        assert diagnostic_scope["eligible_observations"] == 0
        assert (
            write("opportunities/detect", {"require_complete": False})["data"][
                "rules_applied"
            ]
            == []
        )
    elif kind == "zero":
        assert (
            report["groups"][0]["brand_citation_rate"]["denominator"] == 1
            and "GEO-CITE-002" in rules
        )
    elif kind == "missing":
        assert (
            report["groups"][0]["brand_citation_rate"]["denominator"] == 0
            and "GEO-CITE-002" not in rules
        )
    else:
        assert {"GEO-CITE-001", "GEO-MENTION-001"} <= set(rules)
        from test_ai import conv
        from app.ai.schemas import MessageCreate
        from app.ai.models import AIMessage

        opportunity_id = detection["data"]["opportunity_ids"][0]
        conversation = conv((c, r))
        message = r.ai.start(
            conversation["id"],
            MessageCreate(
                content="Phân tích GEO từ collection fixture, không cam kết citation.",
                request_key="live-agent-local-fixture-001",
                geo_scope={
                    "visibility_project_id": pid,
                    "opportunity_id": opportunity_id,
                },
            ),
            submit=False,
        )
        r.ai.run(message["id"])
        with r.db.session() as session:
            saved = session.get(AIMessage, message["id"])
            assert saved.status == "completed", saved.data
            assert (
                saved.data["geo_verification"][
                    "semantic_assertions_automatically_confirmed"
                ]
                is False
            )
            assert session.scalar(select(func.count()).select_from(AIUsage)) == 1
        reviewed = c.patch(
            f"/api/visibility/opportunities/{opportunity_id}/review?project_id={pid}",
            json={
                "status": "approved",
                "notes": "Reviewed synthetic provider evidence; approval performs no website action.",
            },
        )
        assert (
            reviewed.status_code == 200
            and reviewed.json()["review_status"] == "approved"
        )


def test_human_rejection_excludes_evidence_and_provider_output_cannot_be_rewritten(
    live,
):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    result = finish(live)
    oid = result["observation_id"]
    path = f"/api/visibility/observations/{oid}/collection-review?project_id={pid}"
    response = c.post(
        path,
        json={
            "decision": "rejected",
            "reason": "Wrong ownership registry; needs recheck",
        },
    )
    assert response.status_code == 200, response.text
    assert (
        c.get(f"/api/visibility/overview?project_id={pid}").json()[
            "eligible_observations"
        ]
        == 0
    )
    response = c.post(
        path,
        json={
            "decision": "confirmed",
            "reason": "Confirmed original answer and native citations",
        },
    )
    assert response.status_code == 200
    assert (
        c.get(
            f"/api/visibility/overview?project_id={pid}&require_human_review=true"
        ).json()["eligible_observations"]
        == 1
    )
    row = c.get(f"/api/visibility/observations/{oid}?project_id={pid}").json()
    edited = {
        "prompt_id": prompt["id"],
        "provider": "openai_web_search",
        "response_text": "Edited provider answer",
    }
    response = c.post(
        f"/api/visibility/observations/{oid}/corrections?project_id={pid}",
        json={
            "reason": "Try editing immutable provider response",
            "observation": edited,
        },
    )
    assert (
        response.status_code == 409
        and response.json()["code"] == "live_response_immutable"
    )
    assert (
        c.get(f"/api/visibility/observations/{oid}?project_id={pid}").json()[
            "response_text"
        ]
        == row["response_text"]
    )


def test_ingestion_failure_keeps_raw_response_and_usage_without_replay(
    live, monkeypatch
):
    from app.visibility import core

    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    monkeypatch.setattr(
        core, "ingest", Mock(side_effect=RuntimeError("local database failure"))
    )
    result = finish(live)
    assert (
        result["status"] == "FAILED"
        and result["result"]["error_code"] == "live_ingestion_failed"
    )
    assert (
        result["result"]["provider_response"]["id"] == "resp_fixture_001"
        and result["usage"]["estimated_cost_usd"] > 0
    )
    r.visibility_live.run(result["id"])
    assert len(calls) == 2


def test_ambiguous_owned_domain_is_not_zero_citation(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    c.patch(
        f"/api/visibility/entities/{comp['id']}?project_id={pid}",
        json={
            "kind": "competitor",
            "name": "Beta Bags",
            "domains": [{"domain": "acme.test"}],
        },
    )
    result = finish(live)
    group = c.get(f"/api/visibility/overview?project_id={pid}").json()["groups"][0]
    assert group["brand_citation_rate"]["denominator"] == 0
    assert (
        "GEO-CITE-002" not in write("opportunities/detect", {})["data"]["rules_applied"]
    )


GOLDEN = json.loads(
    (
        Path(__file__).parent / "fixtures/visibility/live_reference_cases.json"
    ).read_text()
)["cases"]


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: f"live-golden-{c['id']}")
def test_provider_shaped_golden_reference(case):
    expected = case["expected"]
    if expected["parse_error"]:
        with pytest.raises(ValueError):
            parse_response(
                case["response"],
                "request",
                "prompt",
                "Neutral question",
                {},
                "fixture-model",
            )
        return
    parsed = parse_response(
        case["response"], "request", "prompt", "Neutral question", {}, "fixture-model"
    )
    urls = [c.url for c in parsed["candidate"].citations] if parsed["candidate"] else []
    assert urls == expected["citation_urls"]
    assert (
        parsed["eligible"] == expected["eligible"]
        and parsed["source_count"] == expected["source_count"]
    )
    assert parsed["search_execution"] == expected["search_execution"]
    if parsed["candidate"]:
        assert parsed["candidate"].citation_metadata == expected["citation_metadata"]


def test_double_confirm_is_single_dispatch_under_concurrency(live):
    from concurrent.futures import ThreadPoolExecutor

    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [
            pool.submit(
                r.visibility_live.confirm,
                pid,
                pending["id"],
                confirmation(pending),
                False,
            )
            for _ in range(2)
        ]
        assert all(job.result()["id"] == pending["id"] for job in jobs)
    r.visibility_live.run(pending["id"])
    r.visibility_live.run(pending["id"])
    assert len(calls) == 2
    with r.db.session() as s:
        assert s.scalar(select(func.count()).select_from(AIUsage)) == 1


@pytest.mark.parametrize("usage_kind", ["missing", "oversized_counter"])
def test_unknown_usage_and_uncertain_billing_do_not_invent_total(live, usage_kind):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    r.visibility_live.save_settings(
        cfg.model_copy(update={"search_content_billing": "unverified"})
    )
    pending = preflight(live)
    assert pending["snapshot"]["estimate"]["total_estimate_usd"] is None
    denied = confirmation(pending).model_copy(
        update={"acknowledge_uncertain_cost": False}
    )
    with pytest.raises(GSCError):
        r.visibility_live.confirm(pid, pending["id"], denied, submit=False)
    raw = native_response()
    if usage_kind == "missing":
        raw.pop("usage")
    else:
        raw["usage"]["input_tokens"] = 10**1000
    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
    )
    result = finish(live, pending)
    assert (
        result["status"] == "COMPLETED"
        and result["usage"]["estimated_cost_usd"] is None
    )
    assert (
        "token_usage_missing_or_invalid"
        in result["usage"]["data"]["unknown_cost_components"]
    )


def test_https_fixed_transport_rejects_redirect_and_no_env_proxy(live, monkeypatch):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    redirects = []

    def handler(request):
        redirects.append(str(request.url))
        assert request.headers["authorization"].startswith("Bearer sk-fixture")
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})

    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault, transport=httpx.MockTransport(handler)
    )
    result = finish(live)
    assert redirects == ["https://api.openai.com/v1/responses"]
    assert result["status"] == "FAILED" and not result["observation_id"]


def test_upgrade_006_and_restore_preserve_visibility_review_and_existing_ledger(
    tmp_path,
):
    from alembic import command
    from alembic.config import Config
    from app.db.database import Database, BACKEND
    import sqlite3

    db = Database(tmp_path / "upgrade.db")
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "006_ai_visibility")
        connection.exec_driver_sql(
            "INSERT INTO app_settings VALUES ('phase8-1-preserve','original')"
        )
        from app.visibility.models import VisibilityProject, VisibilityReview

        stamp = datetime.now(timezone.utc).isoformat()
        connection.execute(
            VisibilityProject.__table__.insert(),
            dict(
                id="preserve-project",
                local_project_id="xuong-may",
                name="Existing visibility",
                country="VN",
                language="vi",
                description="original",
                research_goal="preserve",
                status="active",
                created_at=stamp,
                updated_at=stamp,
            ),
        )
        connection.execute(
            VisibilityReview.__table__.insert(),
            dict(
                id="preserve-review",
                project_id="preserve-project",
                entity_type="opportunity",
                entity_id="historical-reference",
                decision="approved",
                data={
                    "notes": "giữ nguyên review",
                    "ratings": {"interpretation": "insufficient_evidence"},
                },
                created_at=stamp,
            ),
        )
        connection.execute(
            AIUsage.__table__.insert(),
            dict(
                id="preserve-usage",
                message_id=None,
                provider="openai",
                model="old-model",
                request_id="old-request",
                status="unknown",
                input_tokens=None,
                output_tokens=None,
                reserved_usd=0.4,
                estimated_cost_usd=None,
                data={"purpose": "existing agent"},
                created_at=stamp,
            ),
        )
        tables = (
            connection.exec_driver_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT IN ('alembic_version','sqlite_sequence') ORDER BY name"
            )
            .scalars()
            .all()
        )
        before = {
            name: connection.exec_driver_sql(f'SELECT * FROM "{name}"').all()
            for name in tables
        }
    source = sqlite3.connect(db.path)
    backup = sqlite3.connect(tmp_path / "backup.db")
    source.backup(backup)
    backup.close()
    source.close()
    db.migrate()
    db.migrate()
    with db.engine.connect() as connection:
        assert all(
            connection.exec_driver_sql(f'SELECT * FROM "{name}"').all() == rows
            for name, rows in before.items()
        )
        assert (
            connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
            and connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
        )
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM sqlite_master WHERE name IN ('visibility_collection_requests','visibility_collection_consents','visibility_search_sources')"
            ).scalar()
            == 3
        )
    source = sqlite3.connect(tmp_path / "backup.db")
    restored = sqlite3.connect(tmp_path / "restore.db")
    source.backup(restored)
    assert (
        restored.execute(
            "SELECT value FROM app_settings WHERE key='phase8-1-preserve'"
        ).fetchone()[0]
        == "original"
    )
    assert (
        restored.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        == "006_ai_visibility"
    )
    assert restored.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    restored.close()
    source.close()
    db.engine.dispose()


def test_credential_changes_at_transport_boundary_never_use_new_account(
    live, monkeypatch
):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    r.visibility_live.confirm(pid, pending["id"], confirmation(pending), submit=False)
    adapter = r.visibility_live.adapter_factory()
    # Simulate rotation after worker validation but before Authorization is built.
    monkeypatch.setattr(adapter, "_key", lambda: "sk-new-account-not-consented-0000")
    r.visibility_live.adapter_factory = lambda: adapter
    r.visibility_live.run(pending["id"])
    result = c.get(
        f"/api/visibility/collection/requests/{pending['id']}?project_id={pid}"
    ).json()
    assert (
        result["result"]["error_code"] == "live_credentials_changed"
        and result["status"] == "FAILED"
    )
    assert result["usage"]["estimated_cost_usd"] == 0 and len(calls) == 1


def test_normalization_failure_keeps_observed_tokens_and_unknown_total(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    raw = native_response()
    raw.pop("model")
    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
    )
    result = finish(live)
    assert result["status"] == "FAILED" and not result["observation_id"]
    assert (
        result["usage"]["input_tokens"] == 350
        and result["usage"]["output_tokens"] == 120
        and result["usage"]["estimated_cost_usd"] is None
    )


@pytest.mark.parametrize("limit,expected_status", [(1, "PARTIAL"), (3, "COMPLETED")])
def test_multiple_search_calls_are_accounted_and_contract_limit_checked(
    live, limit, expected_status
):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    r.visibility_live.save_settings(cfg.model_copy(update={"max_tool_calls": limit}))
    raw = native_response()
    second = copy.deepcopy(raw["output"][1])
    second["id"] = "ws_second"
    raw["output"].append(second)
    r.visibility_live.adapter_factory = lambda: OpenAIWebSearchVisibilityAdapter(
        r.oauth.vault,
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=raw)),
    )
    result = finish(live)
    assert (
        result["status"] == expected_status
        and result["usage"]["data"]["web_search_call_count"] == 2
    )
    assert result["usage"]["data"]["estimated_tool_cost_usd"] == pytest.approx(0.02)


@pytest.mark.parametrize("change", ["prompt", "model"])
def test_prompt_revision_or_model_change_invalidates_consent(live, change):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    if change == "prompt":
        response = c.patch(
            f"/api/visibility/prompts/{prompt['id']}?project_id={pid}",
            json={"text": "A revised exact research question"},
        )
        assert response.status_code == 200
    else:
        r.visibility_live.save_settings(
            cfg.model_copy(update={"model": "another-model"})
        )
    with pytest.raises(GSCError) as error:
        r.visibility_live.confirm(
            pid, pending["id"], confirmation(pending), submit=False
        )
    assert error.value.code == "live_stale_consent" and len(calls) == 1


def test_prompt_context_cannot_change_after_confirm_until_collection_finishes(live):
    c, r, pid, brand, comp, prompt, write, cfg, calls = live
    pending = preflight(live)
    r.visibility_live.confirm(pid, pending["id"], confirmation(pending), submit=False)
    path = f"/api/visibility/prompts/{prompt['id']}?project_id={pid}"
    response = c.patch(
        path,
        json={"text": "Different neutral question", "cohort_type": "brand_specific"},
    )
    assert response.status_code == 409 and response.json()["code"] == "live_prompt_busy"
    assert (
        c.get(f"/api/visibility/prompts/{prompt['id']}?project_id={pid}").json()["text"]
        == prompt["text"]
    )
    r.visibility_live.cancel(pid, pending["id"])
    assert (
        c.patch(
            path, json={"text": "Different neutral question", "cohort_type": "neutral"}
        ).status_code
        == 200
    )
    assert len(calls) == 1
    # A racing edit/confirm is ordered by the same lock: either edit first and
    # consent becomes stale, or confirmation first and edit is refused.
    from concurrent.futures import ThreadPoolExecutor

    pending = preflight(live, "fixture-prompt-edit-race-0001")

    def confirm_racing():
        try:
            return r.visibility_live.confirm(
                pid, pending["id"], confirmation(pending), submit=False
            )["status"]
        except GSCError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        confirmation_job = pool.submit(confirm_racing)
        edit_job = pool.submit(
            c.patch,
            path,
            json={"text": "Third research question", "cohort_type": "neutral"},
        )
        outcome, edit_result = confirmation_job.result(), edit_job.result()
    assert (outcome, edit_result.status_code) in (
        ("QUEUED", 409),
        ("live_stale_consent", 200),
    )
    r.visibility_live.cancel(pid, pending["id"])
    assert len(calls) == 1
