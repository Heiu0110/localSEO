"""Phase 8 reference fixtures, immutable imports, denominators and project boundaries."""

import json
import unicodedata
from pathlib import Path
from unittest.mock import Mock
import pytest
from sqlalchemy import select, func
from test_ai import env
from app.visibility import extraction, core
from app.visibility.models import *
from app.ai.schemas import MessageCreate
from app.ai.models import AIMessage
from test_ai import conv


@pytest.fixture
def visibility(env):
    client, runtime = env
    result = client.post(
        "/api/visibility/projects",
        json={"local_project_id": "xuong-may", "name": "Brand fixture"},
    )
    assert result.status_code == 201, result.text
    pid = result.json()["id"]

    def write(path, data):
        result = client.post(f"/api/visibility/{path}?project_id={pid}", json=data)
        assert result.status_code < 300, result.text
        return result.json()

    brand = write(
        "entities",
        {
            "name": "Acme Balo",
            "aliases": [{"name": "Acme Bags"}, {"name": "Sen", "ambiguous": True}],
            "domains": [{"domain": "acme.test"}],
        },
    )
    competitor = write(
        "entities",
        {
            "kind": "competitor",
            "name": "Beta Bags",
            "aliases": [],
            "domains": [{"domain": "beta.test"}],
        },
    )
    prompt = write(
        "prompts",
        {
            "text": "Những xưởng may balo nào phù hợp?",
            "topic": "may balo",
            "intent": "commercial",
        },
    )
    return client, runtime, pid, brand, competitor, prompt, write


def observed(prompt, text, **extra):
    return {
        "prompt_id": prompt["id"],
        "provider": "provider-fixture",
        "model": "model-one",
        "response_text": text,
        "observed_at": "2026-10-20T08:00:00+07:00",
        "country": "VN",
        "language": "vi",
        "grounding": "enabled",
        **extra,
    }


def test_bootstrap_manual_evidence_and_distinct_denominators(visibility):
    client, runtime, pid, brand, competitor, prompt, write = visibility
    text = "  Acme Balo và Beta Bags. https://acme.test/catalog  \n"
    row = write("observations", observed(prompt, text))
    assert row["response_text"] == text
    assert {
        m["entity_id"] for m in row["mentions"] if m["status"] == "CONFIRMED_MATCH"
    } == {brand["id"], competitor["id"]}
    assert (
        row["citations"] == []
        and row["extraction"]["data"]["url_mentions"][0]["is_citation"] is False
    )
    report = client.get(f"/api/visibility/overview?project_id={pid}")
    assert report.status_code == 200, report.text
    group = report.json()["groups"][0]
    assert group["brand_mention_rate"] == {
        "numerator": 1,
        "denominator": 1,
        "percent": 100,
    }
    assert (
        group["brand_citation_rate"]["denominator"] == 0
        and group["brand_citation_rate"]["percent"] is None
    )
    second = write(
        "observations",
        observed(
            prompt,
            "Acme Balo được nhắc.",
            citation_capability="capable",
            citation_metadata="complete",
        ),
    )
    group = client.get(f"/api/visibility/overview?project_id={pid}").json()["groups"][0]
    assert group["brand_citation_rate"] == {
        "numerator": 0,
        "denominator": 1,
        "percent": 0,
    }
    detected = write("opportunities/detect", {})
    assert "GEO-CITE-002" in detected["data"]["rules_applied"]
    assert "GEO-MENTION-001" not in detected["data"]["rules_applied"]


def test_citation_normalization_and_no_partial_domain_ownership():
    assert (
        extraction.normalize_url(
            "HTTPS://EXAMPLE.COM:443/a%7e?q=%2f&tokenid=1#fragment"
        )
        == "https://example.com/a~?q=%2F&tokenid=1"
    )
    entity = {
        "id": "brand",
        "kind": "brand",
        "name": "Example",
        "config": {"domains": [{"domain": "example.com", "include_subdomains": False}]},
    }
    assert extraction.ownership("https://example.com/x", [entity]) == (
        "OWNED_BRAND",
        "brand",
    )
    assert (
        extraction.ownership("https://example.com.vn/x", [entity])[0] == "THIRD_PARTY"
    )
    assert (
        extraction.ownership("https://docs.example.com/x", [entity])[0] == "THIRD_PARTY"
    )
    entity["config"]["domains"][0]["include_subdomains"] = True
    assert (
        extraction.ownership("https://docs.example.com/x", [entity])[0] == "OWNED_BRAND"
    )
    for url in (
        "javascript:alert(1)",
        "https://u:p@example.com",
        "https://example.com/%ZZ",
    ):
        with pytest.raises(ValueError):
            extraction.normalize_url(url)


def test_ambiguous_accents_overlap_and_original_span():
    registry = [
        {
            "id": "a",
            "kind": "brand",
            "name": "Sen",
            "config": {"ambiguous": True, "aliases": [{"name": "Đẹp Balo"}]},
        }
    ]
    text = "Hoa Sen và " + unicodedata.normalize("NFD", "Đẹp Balo")
    rows = extraction.mentions(text, registry)
    assert next(r for r in rows if r["alias"] == "Sen")["status"] == "NEEDS_REVIEW"
    exact = next(r for r in rows if r["alias"] == "Đẹp Balo")
    assert exact["status"] == "CONFIRMED_MATCH" and text[
        exact["start"] : exact["end"]
    ] == unicodedata.normalize("NFD", "Đẹp Balo")
    assert extraction.mentions("Dep Balo", registry)[0]["status"] == "POSSIBLE_MATCH"
    registry.append({"id": "b", "kind": "competitor", "name": "Đẹp Balo", "config": {}})
    assert all(
        r["status"] == "NEEDS_REVIEW" for r in extraction.mentions("Đẹp Balo", registry)
    )


def test_existing_agent_offline_geo_analysis_and_evidence_gate(visibility):
    client, runtime, pid, brand, competitor, prompt, write = visibility
    write("observations", observed(prompt, "Beta Bags được nhắc trong tập mẫu này."))
    detected = write("opportunities/detect", {})
    oid = detected["data"]["opportunity_ids"][0]
    conversation = conv((client, runtime))
    message = runtime.ai.start(
        conversation["id"],
        MessageCreate(
            content="Phân tích cơ hội GEO đã chọn.",
            request_key="geo-fixture-local-001",
            geo_scope={"visibility_project_id": pid, "opportunity_id": oid},
        ),
        submit=False,
    )
    runtime.ai.run(message["id"])
    with runtime.db.session() as s:
        record = s.get(AIMessage, message["id"])
        assert record.status == "completed", record.data
        assert record.data["analysis"]["geo_analysis"]["project_id"] == pid
        saved = s.scalar(
            select(VisibilityAgentAnalysis).where(
                VisibilityAgentAnalysis.message_id == message["id"]
            )
        )
        assert saved.data["status"] == "Needs Human Verification"
        assert saved.data["semantic_assertions_automatically_confirmed"] is False
    assert (
        runtime.ai.registry.execute(
            "get_geo_opportunities", {"visibility_id": pid}, "xuong-may"
        )["evidence"]["source_type"]
        == "AI Visibility"
    )


REFERENCE = json.loads(
    (Path(__file__).parent / "fixtures/visibility/reference_cases.json").read_text()
)


@pytest.mark.parametrize(
    "case", [x for x in REFERENCE if "text" in x], ids=lambda x: f"reference-{x['id']}"
)
def test_reference_extraction(visibility, case):
    c, r, pid, brand, competitor, prompt, write = visibility
    citations = (
        [
            {
                "url": case["citation_url"],
                "source_type": "provider_annotation",
                **(
                    {"reported_domain": case["reported_domain"]}
                    if "reported_domain" in case
                    else {}
                ),
            }
        ]
        if "citation_url" in case
        else []
    )
    row = write(
        "observations",
        observed(
            prompt,
            case["text"],
            citations=citations,
            citation_capability=(
                "capable" if case.get("capable") or citations else "unknown"
            ),
            citation_metadata=(
                "complete" if case.get("capable") or citations else "missing"
            ),
        ),
    )
    confirmed = {
        m["entity_id"] for m in row["mentions"] if m["status"] == "CONFIRMED_MATCH"
    }
    assert (brand["id"] in confirmed) == case["brand"]
    assert (competitor["id"] in confirmed) == case["competitor"]
    matched = [
        x
        for x in row["citations"]
        if x["attribution_status"] == "CONFIRMED_ATTRIBUTION"
    ]
    assert len(matched) == case["citations"]
    if case.get("owner"):
        assert matched[0]["ownership"] == case["owner"]
    if case.get("url_mentions"):
        assert len(row["extraction"]["data"]["url_mentions"]) == case["url_mentions"]
    if case.get("abstain"):
        assert any(
            x["status"] in ("NEEDS_REVIEW", "POSSIBLE_MATCH") for x in row["mentions"]
        ) or any(x["attribution_status"] == "NEEDS_REVIEW" for x in row["citations"])
    overview = c.get(f"/api/visibility/overview?project_id={pid}").json()["groups"][0]
    assert overview["brand_mention_rate"]["numerator"] == int(case["brand"])
    if case["id"] in (11, 12):
        assert overview["brand_citation_rate"]["denominator"] == (
            1 if case["id"] == 12 else 0
        )
    if case["id"] == 24:
        assert (
            len(row["mentions"]) == 2
            and overview["brand_mention_rate"]["numerator"] == 1
        )
    rule = {
        4: "GEO-MENTION-001",
        5: "GEO-CITE-001",
        9: "GEO-CITE-002",
        10: "GEO-CITE-003",
    }.get(case["id"])
    if rule:
        assert rule in write("opportunities/detect", {})["data"]["rules_applied"]


def report(c, pid, **scope):
    return c.get("/api/visibility/overview", params={"project_id": pid, **scope}).json()


@pytest.mark.parametrize(
    "scenario", [x["scenario"] for x in REFERENCE if "scenario" in x]
)
def test_reference_scenarios(visibility, scenario, monkeypatch):
    from app.visibility import engine, evidence, verification, agent_integration
    from app.visibility.schemas import Cohort
    from app.gsc.errors import GSCError

    c, runtime, pid, brand, competitor, prompt, write = visibility
    if scenario == "dedup":
        data = observed(prompt, "Acme Balo trùng import")
        job = write("observations/import-preview", {"rows": [data, data]})
        assert report(c, pid)["stored_observations"] == 0
        imported = write(
            "observations/import-commit", {"job_id": job["id"], "confirm": True}
        )
        assert imported["data"]["created"] == 1 and imported["data"]["duplicates"] == 1
        assert (
            write("observations/import-commit", {"job_id": job["id"], "confirm": True})[
                "data"
            ]
            == imported["data"]
        )
        assert report(c, pid)["stored_observations"] == 1
        raw = c.get(
            f"/api/visibility/observations/{imported['data']['record_ids'][0]}?project_id={pid}"
        ).json()
        assert raw["original"]["import_provenance"]["job_id"] == job["id"]
    elif scenario == "providers":
        write("observations", observed(prompt, "Acme Balo"))
        write(
            "observations",
            observed(prompt, "Beta Bags", provider="different", model="model-two"),
        )
        data = report(c, pid)
        assert len(data["groups"]) == 2 and data["cross_provider_comparable"] is False
        assert sorted(g["brand_mention_rate"]["percent"] for g in data["groups"]) == [
            0,
            100,
        ]
    elif scenario == "dates":
        write("observations", observed(prompt, "Acme Balo"))
        write(
            "observations",
            observed(prompt, "Acme Balo", observed_at="2026-10-21T08:00:00+07:00"),
        )
        assert report(c, pid)["eligible_observations"] == 2
        assert (
            report(c, pid, start="2026-10-20", end="2026-10-20")[
                "eligible_observations"
            ]
            == 1
        )
    elif scenario == "branded":
        write("observations", observed(prompt, "Acme Balo"))
        branded = write(
            "prompts", {"text": "Acme Balo có tốt không?", "cohort_type": "neutral"}
        )
        write("observations", observed(branded, "Acme Balo"))
        assert report(c, pid)["eligible_observations"] == 1
        all_data = report(c, pid, cohort_type="all")
        assert len(all_data["groups"]) == 2
        assert {x["cohort"]["cohort_type"] for x in all_data["groups"]} == {
            "neutral",
            "brand_specific",
        }
        assert report(c, pid)["prompt_coverage"]["denominator"] == 1
    elif scenario == "incomplete":
        write("observations", observed(prompt, "Beta Bags", completeness="partial"))
        assert report(c, pid)["eligible_observations"] == 0
        assert report(c, pid)["exclusion_counts"] == {"incomplete_observation": 1}
        assert not write("opportunities/detect", {})["data"]["opportunity_ids"]
    elif scenario in ("technical", "technical_stale"):
        stale = scenario.endswith("stale")
        from test_ai import technical
        from app.technical.models import AuditIssue, AuditURL, AuditRun
        from datetime import datetime, timezone, timedelta

        tp, audit = technical((c, runtime))
        with runtime.db.session.begin() as session:
            session.get(VisibilityProject, pid).local_project_id = "audit:" + tp.id
            page = session.scalar(
                select(AuditURL).where(
                    AuditURL.audit_id == audit.id, AuditURL.state == "fetched"
                )
            )
            assert page
            from app.ai.common import now

            issue = AuditIssue(
                id="reference-noindex",
                audit_id=audit.id,
                project_id=tp.id,
                url_id=page.id,
                fingerprint="reference-noindex",
                url=page.url,
                rule_id="INDEX-002",
                category="INDEX",
                title="Reference noindex on expected URL",
                severity="high",
                confidence="confirmed",
                evidence_type="fixture",
                evidence={"meta_robots": "noindex", "expected_index": True},
                recommendation="Review index intent",
                verification="Inspect current source",
                priority=80,
                priority_reasons=["fixture"],
                first_seen_at=now(),
                last_seen_at=now(),
            )
            session.add(issue)
            target = page.url
            timestamp = (
                datetime.now(timezone.utc) - timedelta(days=90 if stale else 0)
            ).isoformat()
            page.crawled_at = timestamp
            session.get(AuditRun, audit.id).started_at = timestamp
        patched = c.patch(
            f"/api/visibility/prompts/{prompt['id']}?project_id={pid}",
            json={"text": prompt["text"], "target_url": target},
        )
        assert patched.status_code == 200, patched.text
        run = write("opportunities/detect", {})
        assert run["data"]["rules_applied"] == ["GEO-TECH-001"]
        item = c.get(
            f"/api/visibility/opportunities/{run['data']['opportunity_ids'][0]}?project_id={pid}"
        ).json()
        assert item["priority"] == ("Investigation" if stale else "P1")
        assert "Chưa chứng minh" in str(item["missing_information"])
    elif scenario in ("invented", "causal"):
        write("observations", observed(prompt, "Beta Bags"))
        run = write("opportunities/detect", {})
        with runtime.db.session() as s:
            p = s.get(VisibilityProject, pid)
            op = s.get(VisibilityOpportunity, run["data"]["opportunity_ids"][0])
            packet = agent_integration.context_packet(s, p, op, runtime.db)
            geo = agent_integration.local_analysis(packet, "envelope")["geo_analysis"]
            if scenario == "invented":
                geo["findings"][0]["evidence_ids"] = ["nonexistent-id"]
                with pytest.raises(GSCError) as error:
                    verification.verify(
                        s, p, op, geo, packet["available_evidence_ids"], runtime.db
                    )
                assert error.value.code == "geo_invented_evidence"
            else:
                geo["findings"][0][
                    "explanation"
                ] = "Noindex là nguyên nhân duy nhất khiến AI không nhắc brand."
                with pytest.raises(GSCError) as error:
                    verification.verify(
                        s, p, op, geo, packet["available_evidence_ids"], runtime.db
                    )
                assert error.value.code == "geo_unsupported_claim"
                geo["findings"][0].update(
                    predicate="hypothesis",
                    explanation="Có thể do nội dung chưa rõ; cần kiểm tra thêm.",
                )
                geo["opportunities"][0].update(
                    action_type="Improve Existing Content",
                    priority="P0",
                    evidence_confidence="Verified",
                )
                verified = verification.verify(
                    s, p, op, geo, packet["available_evidence_ids"], runtime.db
                )
                assert (
                    verified["claims_needing_human_verification"]
                    and verified["downgrades"]
                )
                assert (
                    verified["analysis"]["opportunities"][0]["action_type"]
                    == "Investigate"
                )
                assert (
                    verified["analysis"]["opportunities"][0]["evidence_confidence"]
                    == op.data["evidence_confidence"]
                )
    elif scenario == "shared_domain":
        other = write("prompts", {"text": "Nhà cung cấp balo cho doanh nghiệp?"})
        for item in (prompt, other):
            row = write(
                "observations",
                observed(
                    item,
                    "Theo nguồn độc lập.",
                    citations=[
                        {
                            "url": "https://shared.test/post",
                            "source_type": "provider_annotation",
                        }
                    ],
                ),
            )
            assert (
                row["citations"][0]["ownership"] == "THIRD_PARTY"
                and row["citations"][0]["entity_id"] is None
            )
        assert (
            "GEO-SOURCE-001"
            in write("opportunities/detect", {})["data"]["rules_applied"]
        )
    elif scenario == "identity":
        for phone in ("0123456789", "0987654321"):
            write(
                "documents",
                {
                    "kind": "business_identity",
                    "content": f"Acme Balo: {phone}",
                    "source_name": "User supplied business source",
                    "approved": True,
                    "verification": "user_verified",
                    "entity_id": brand["id"],
                    "business_fields": {"phone": phone},
                },
            )
        assert (
            "GEO-ENTITY-001"
            in write("opportunities/detect", {})["data"]["rules_applied"]
        )
    elif scenario == "no_action":
        for day in range(1, 21):
            write(
                "observations",
                observed(
                    prompt,
                    "Acme Balo có nguồn tham khảo.",
                    observed_at=f"2026-10-{day:02d}T08:00:00+07:00",
                    citation_capability="capable",
                    citation_metadata="complete",
                    citations=[
                        {
                            "url": "https://acme.test/a",
                            "source_type": "provider_annotation",
                        }
                    ],
                ),
            )
        run = write("opportunities/detect", {})
        assert len(run["data"]["included_observation_ids"]) == 20
        assert (
            run["data"]["opportunity_ids"] == []
            and len(run["data"]["abstentions"]) == 9
        )


def test_import_atomic_validation_expiry_staleness_and_original_file(visibility):
    from datetime import datetime, timezone, timedelta

    c, r, pid, brand, competitor, prompt, write = visibility
    good = observed(prompt, "  Acme Balo\n exact whitespace  ")
    bad = {**good, "prompt_id": "wrong-project"}
    preview = write("observations/import-preview", {"rows": [good, bad]})
    assert (
        preview["data"]["validated_rows"] == 1 and len(preview["data"]["errors"]) == 1
    )
    result = c.post(
        f"/api/visibility/observations/import-commit?project_id={pid}",
        json={"job_id": preview["id"], "confirm": True},
    )
    assert result.status_code == 409 and report(c, pid)["stored_observations"] == 0
    content = json.dumps([good], ensure_ascii=False).encode()
    response = c.post(
        f"/api/visibility/observations/file-preview?project_id={pid}",
        files={"file": ("observations.json", content, "application/json")},
    )
    assert response.status_code == 200, response.text
    job = response.json()
    assert (
        job["data"]["file"]["sha256"]
        == __import__("hashlib").sha256(content).hexdigest()
    )
    with r.db.session.begin() as s:
        s.get(VisibilityImportJob, job["id"]).created_at = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
    assert (
        c.post(
            f"/api/visibility/observations/import-commit?project_id={pid}",
            json={"job_id": job["id"], "confirm": True},
        ).status_code
        == 409
    )
    job = c.post(
        f"/api/visibility/observations/file-preview?project_id={pid}",
        files={"file": ("observations.json", content, "application/json")},
    ).json()
    imported = write(
        "observations/import-commit", {"job_id": job["id"], "confirm": True}
    )
    row = c.get(
        f"/api/visibility/observations/{imported['data']['record_ids'][0]}?project_id={pid}"
    ).json()
    assert (
        row["response_text"] == good["response_text"]
        and row["original"]["import_provenance"]["file"]["name"] == "observations.json"
    )
    pending = write(
        "observations/import-preview",
        {"rows": [observed(prompt, "A different response")]},
    )
    write("entities", {"kind": "competitor", "name": "Additional brand"})
    assert (
        c.post(
            f"/api/visibility/observations/import-commit?project_id={pid}",
            json={"job_id": pending["id"], "confirm": True},
        ).status_code
        == 409
    )


def test_correction_revision_review_and_stale_agent_evidence(visibility):
    from app.visibility import verification
    from app.gsc.errors import GSCError

    c, r, pid, brand, competitor, prompt, write = visibility
    data = observed(prompt, "Beta Bags là tên được nhắc.")
    original = write("observations", data)
    run = write("opportunities/detect", {})
    oid = run["data"]["opportunity_ids"][0]
    old = c.get(f"/api/visibility/opportunities/{oid}?project_id={pid}").json()
    corrected = write(
        f"observations/{original['id']}/corrections",
        {
            "observation": {**data, "response_text": "Acme Balo được nhắc ở bản sửa."},
            "reason": "Sửa phản hồi đã dán sai.",
        },
    )
    assert corrected["supersedes_id"] == original["id"]
    saved = c.get(
        f"/api/visibility/observations/{original['id']}?project_id={pid}"
    ).json()
    assert (
        saved["response_text"] == data["response_text"]
        and saved["extraction"]["id"] == original["extraction"]["id"]
    )
    assert report(c, pid)["eligible_observations"] == 1
    with r.db.session() as s:
        with pytest.raises(GSCError) as error:
            verification.check_evidence(
                s, s.get(VisibilityProject, pid), old["evidence_ids"][0], r.db
            )
        assert error.value.code == "geo_stale_evidence"
    mention = corrected["mentions"][0]
    reviewed = c.patch(
        f"/api/visibility/mentions/{mention['id']}/review?project_id={pid}",
        json={"status": "REJECTED_MATCH", "reason": "Manual decision for evaluation"},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert report(c, pid)["groups"][0]["brand_mention_rate"]["numerator"] == 0
    revised = write(f"observations/{corrected['id']}/extract", {"confirm": True})
    assert revised["extraction"]["revision"] == 2
    with r.db.session() as s:
        assert s.get(VisibilityMention, mention["id"]).status == "REJECTED_MATCH"
        assert (
            s.scalar(
                select(func.count())
                .select_from(VisibilityReview)
                .where(VisibilityReview.project_id == pid)
            )
            >= 1
        )


def test_project_scope_all_references_and_agent_tools_are_read_only(visibility):
    from app.gsc.errors import GSCError
    from app.ai.schemas import MessageCreate

    c, r, pid, brand, competitor, prompt, write = visibility
    row = write("observations", observed(prompt, "Beta Bags"))
    run = write("opportunities/detect", {})
    oid = run["data"]["opportunity_ids"][0]
    other = c.post(
        "/api/visibility/projects",
        json={"local_project_id": "xuong-may", "name": "Other visibility"},
    ).json()["id"]
    for path in (f"observations/{row['id']}", f"opportunities/{oid}"):
        assert c.get(f"/api/visibility/{path}?project_id={other}").status_code == 403
    invalid = c.post(
        f"/api/visibility/observations?project_id={other}",
        json=observed(prompt, "cross project"),
    )
    assert invalid.status_code == 403
    job = write("observations/import-preview", {"rows": [observed(prompt, "pending")]})
    assert (
        c.post(
            f"/api/visibility/observations/import-commit?project_id={other}",
            json={"job_id": job["id"], "confirm": True},
        ).status_code
        == 403
    )
    conversation = conv((c, r), project="cong-ty")
    with pytest.raises(GSCError):
        r.ai.start(
            conversation["id"],
            MessageCreate(
                content="Analyze GEO",
                request_key="cross-project-geo",
                geo_scope={"visibility_project_id": pid, "opportunity_id": oid},
            ),
            submit=False,
        )
    with r.db.session() as s:
        before = [
            s.scalar(select(func.count()).select_from(model))
            for model in (
                VisibilityObservation,
                VisibilityOpportunity,
                VisibilityReview,
            )
        ]
    args = {"visibility_id": pid, "observation_id": row["id"], "opportunity_id": oid}
    from app.visibility.agent_tools import SPECS

    for name, (schema, _) in SPECS.items():
        values = {k: v for k, v in args.items() if k in schema.model_fields}
        result = r.ai.registry.execute(name, values, "xuong-may")
        assert "evidence" in result and len(json.dumps(result).encode()) < 12000
        with pytest.raises(GSCError):
            r.ai.registry.execute(name, values, "cong-ty")
    with r.db.session() as s:
        assert before == [
            s.scalar(select(func.count()).select_from(model))
            for model in (
                VisibilityObservation,
                VisibilityOpportunity,
                VisibilityReview,
            )
        ]


@pytest.mark.parametrize(
    "raw",
    [
        {"annotations": "broken"},
        {"annotations": [None]},
        {"annotations": [{"type": "url_citation", "url_citation": None}]},
        {
            "output": [
                {
                    "content": [
                        {
                            "annotations": [
                                {"type": "url_citation", "url": "javascript:alert(1)"}
                            ]
                        }
                    ]
                }
            ]
        },
    ],
)
def test_malformed_annotations_never_create_false_zero_or_fetch(visibility, raw):
    c, r, pid, brand, competitor, prompt, write = visibility
    row = write(
        "observations",
        observed(
            prompt,
            "Acme Balo <script>alert('xss')</script>",
            raw_annotations=raw,
            citation_capability="capable",
            citation_metadata="complete",
        ),
    )
    assert row["response_text"].endswith("</script>")
    assert row["extraction"]["data"]["warnings"]
    assert report(c, pid)["groups"][0]["brand_citation_rate"]["denominator"] == 0


def test_native_grounding_utf16_csv_injection_and_sanitized_validation(visibility):
    from app.visibility.files import export

    c, r, pid, brand, competitor, prompt, write = visibility
    text = "😀 Acme Balo"
    row = write(
        "observations",
        observed(
            prompt,
            text,
            citations=[
                {
                    "url": "https://acme.test/a",
                    "source_type": "provider_annotation",
                    "start": 3,
                    "end": 12,
                    "offset_unit": "utf16",
                    "quote": "Acme Balo",
                }
            ],
            citation_capability="capable",
            citation_metadata="complete",
        ),
    )
    assert row["citations"][0]["attribution_status"] == "CONFIRMED_ATTRIBUTION"
    assert row["citations"][0]["data"]["start"] == 2
    ground = {
        "groundingMetadata": {
            "groundingChunks": [
                {"web": {"uri": "https://acme.test/a"}},
                {"web": {"uri": "https://beta.test/b"}},
            ],
            "groundingSupports": [
                {
                    "segment": {"startIndex": 0, "endIndex": 9, "text": "Acme Balo"},
                    "groundingChunkIndices": [0],
                }
            ],
        }
    }
    row = write(
        "observations",
        observed(
            prompt,
            "Acme Balo",
            raw_annotations=ground,
            citation_capability="capable",
            citation_metadata="complete",
        ),
    )
    assert (
        len(row["citations"]) == 1
        and row["citations"][0]["source_type"] == "grounding_metadata"
    )
    assert row["extraction"]["data"]["citation_complete"] is False
    csv, _ = export([{"text": '  =HYPERLINK("x")'}], "csv")
    assert "'  =" in csv.decode()
    secret = "sk-proj-" + "x" * 30
    rejected = c.post(
        f"/api/visibility/observations?project_id={pid}", json=observed(prompt, secret)
    )
    assert rejected.status_code == 422 and secret not in rejected.text
    assert (
        c.post(
            f"/api/visibility/entities?project_id={pid}",
            json={
                "name": "Bad profile",
                "kind": "competitor",
                "social_profiles": ["https://social.test/"],
            },
        ).status_code
        == 422
    )


def test_ambiguous_brand_does_not_prove_absence_and_review_is_not_execution(visibility):
    c, r, pid, brand, competitor, prompt, write = visibility
    write("observations", observed(prompt, "Sen và Beta Bags cùng xuất hiện."))
    run = write("opportunities/detect", {})
    assert "GEO-MENTION-001" not in run["data"]["rules_applied"]
    write("observations", observed(prompt, "Beta Bags được nhắc riêng."))
    run = write("opportunities/detect", {})
    oid = run["data"]["opportunity_ids"][0]
    review = c.patch(
        f"/api/visibility/opportunities/{oid}/review?project_id={pid}",
        json={
            "status": "approved",
            "notes": "Approved for investigation",
            "ratings": {"interpretation": "insufficient_evidence"},
        },
    )
    assert review.status_code == 200, review.text
    assert review.json()["review_status"] == "approved"
    again = write("opportunities/detect", {})
    assert oid in again["data"]["opportunity_ids"]
    assert (
        c.get(f"/api/visibility/opportunities/{oid}?project_id={pid}").json()[
            "review_status"
        ]
        == "approved"
    )


def test_content_gap_requires_actual_page_approved_requirement_and_human_coverage(
    visibility,
):
    c, r, pid, brand, competitor, prompt, write = visibility
    req = write(
        "documents",
        {
            "kind": "topic_requirement",
            "content": "Cần giải thích quy trình và tiêu chuẩn kiểm tra chất lượng.",
            "source_name": "Business requirement",
            "approved": True,
            "prompt_ids": [prompt["id"]],
        },
    )
    page = write(
        "documents",
        {
            "kind": "page_content",
            "content": "Nội dung trang đã nhập: giới thiệu sản phẩm hiện tại.",
            "source_name": "Saved page copy",
            "url": "https://acme.test/page",
            "approved": True,
        },
    )
    assert not write("opportunities/detect", {})["data"]["opportunity_ids"]
    write(
        "coverage-reviews",
        {
            "requirement_id": req["id"],
            "page_id": page["id"],
            "decision": "missing",
            "reason": "Đã đọc trang, chưa có quy trình/tiêu chuẩn tương đương.",
        },
    )
    run = write("opportunities/detect", {})
    assert run["data"]["rules_applied"] == ["GEO-CONTENT-001"]
    c.patch(
        f"/api/visibility/documents/{page['id']}/review?project_id={pid}",
        json={"approved": False, "reason": "Nguồn đã hết hiệu lực"},
    )
    assert not write("opportunities/detect", {})["data"]["opportunity_ids"]


def test_geo_cloud_reuses_consent_budget_and_structured_schema(visibility):
    from test_ai import enable, analysis_for
    from app.visibility import agent_integration
    from app.gsc.errors import GSCError

    c, r, pid, brand, competitor, prompt, write = visibility
    write("observations", observed(prompt, "Beta Bags"))
    oid = write("opportunities/detect", {})["data"]["opportunity_ids"][0]
    with r.db.session() as s:
        packet = agent_integration.context_packet(
            s, s.get(VisibilityProject, pid), s.get(VisibilityOpportunity, oid), r.db
        )

    class FakeGEOProvider:
        def __init__(self):
            self.calls = []

        def validate(self, model):
            return {"model": model, "validated_at": "2026-10-30"}

        def respond(self, payload):
            self.calls.append(payload)
            assert len(json.dumps(payload, ensure_ascii=False).encode()) <= 48000
            result = analysis_for(payload)
            result["geo_analysis"] = agent_integration.local_analysis(
                packet, "fixture"
            )["geo_analysis"]
            result["geo_analysis"]["opportunities"][0].update(
                action_type="Improve Existing Content",
                priority="P0",
                recommended_action="Thay đổi nội dung ngay.",
            )
            result["recommendations"][0][
                "proposed_action"
            ] = "Ungated generic change must be replaced."
            return {
                "id": "resp_geo_fixture",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(result, ensure_ascii=False),
                            }
                        ],
                    }
                ],
                "usage": {"input_tokens": 200, "output_tokens": 100},
            }

    fake = FakeGEOProvider()
    cfg = enable((c, r), fake)
    conversation = conv((c, r), provider="openai")
    body = {
        "content": "Phân tích cơ hội GEO.",
        "request_key": "geo-cloud-explicit-consent",
        "provider": "openai",
        "geo_scope": {"visibility_project_id": pid, "opportunity_id": oid},
    }
    with pytest.raises(GSCError):
        r.ai.start(conversation["id"], MessageCreate(**body), submit=False)
    assert fake.calls == []
    from app.ai.provider import turn_estimate

    body.update(
        acknowledge_external_processing=True,
        approved_model=cfg.model,
        approved_max_estimate_usd=turn_estimate(cfg)["turn_upper_estimate_usd"],
    )
    msg = r.ai.start(conversation["id"], MessageCreate(**body), submit=False)
    r.ai.run(msg["id"])
    with r.db.session() as s:
        saved = s.get(AIMessage, msg["id"])
        assert saved.status == "completed", saved.data
        assert saved.data["tool_calls"] == 2
        assert (
            saved.data["analysis"]["geo_analysis"]["opportunities"][0]["action_type"]
            == "Investigate"
        )
        assert "Ungated generic" not in str(saved.data["analysis"]["recommendations"])
        assert (
            "chưa thực hiện"
            in saved.data["analysis"]["recommendations"][0]["proposed_action"]
        )
        assert (
            saved.data["geo_verification"][
                "semantic_assertions_automatically_confirmed"
            ]
            is False
        )
    schema = fake.calls[0]["text"]["format"]["schema"]
    assert "geo_analysis" in schema["properties"]


def test_additive_migration_preserves_all_existing_tables_and_values(tmp_path):
    from alembic import command
    from alembic.config import Config
    from app.db.database import Database, BACKEND

    db = Database(tmp_path / "preservation.db")
    config = Config()
    config.set_main_option("script_location", str(BACKEND / "migrations"))
    with db.engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "005_keyword_serp_research")
        connection.exec_driver_sql(
            'INSERT INTO app_settings (key,value) VALUES (\'phase8-preserve\',\'{"value":17,"text":"nguyên vẹn"}\')'
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
    db.migrate()
    db.migrate()
    with db.engine.connect() as connection:
        assert all(
            connection.exec_driver_sql(f'SELECT * FROM "{name}"').all() == rows
            for name, rows in before.items()
        )
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name LIKE 'visibility_%'"
            ).scalar()
            == 15
        )
        assert connection.exec_driver_sql("PRAGMA integrity_check").scalar() == "ok"
        assert connection.exec_driver_sql("PRAGMA foreign_key_check").all() == []
    db.engine.dispose()


def test_priority_topic_mapping_candidate_and_stale_reference_gate(visibility):
    from app.visibility import verification
    from app.gsc.errors import GSCError

    c, r, pid, brand, competitor, prompt, write = visibility
    response = c.patch(
        f"/api/visibility/prompts/{prompt['id']}?project_id={pid}",
        json={"text": prompt["text"], "priority": 2, "topic": "May balo theo yêu cầu"},
    )
    assert response.status_code == 200, response.text
    run = write("opportunities/detect", {})
    assert run["data"]["rules_applied"] == ["GEO-TOPIC-001"]
    oid = run["data"]["opportunity_ids"][0]
    detail = c.get(f"/api/visibility/opportunities/{oid}?project_id={pid}").json()
    assert detail["action_type"] == "Investigate" and detail["priority"] != "P0"
    c.patch(
        f"/api/visibility/prompts/{prompt['id']}?project_id={pid}",
        json={
            "text": prompt["text"],
            "priority": 2,
            "target_url": "https://acme.test/mapped",
        },
    )
    assert not write("opportunities/detect", {})["data"]["opportunity_ids"]
    with r.db.session() as s:
        with pytest.raises(GSCError) as error:
            verification.check_evidence(
                s, s.get(VisibilityProject, pid), detail["evidence_ids"][0], r.db
            )
        assert error.value.code == "geo_stale_evidence"


@pytest.mark.parametrize(
    "raw",
    [
        {"groundingMetadata": {"groundingChunks": "broken"}},
        {"groundingMetadata": {"groundingSupports": [{"groundingChunkIndices": [99]}]}},
        {"groundingMetadata": None},
        {"output": [{"content": [{"annotations": "broken"}]}]},
        {"annotations": [{"type": "file_citation", "file_id": "unavailable"}]},
    ],
)
def test_unsupported_or_malformed_grounding_is_not_complete_zero(visibility, raw):
    c, r, pid, brand, competitor, prompt, write = visibility
    row = write(
        "observations",
        observed(
            prompt,
            "Acme Balo",
            raw_annotations=raw,
            citation_capability="capable",
            citation_metadata="complete",
        ),
    )
    assert row["extraction"]["data"]["warnings"]
    assert row["extraction"]["data"]["citation_complete"] is False
    assert report(c, pid)["groups"][0]["brand_citation_rate"]["percent"] is None
