#!/usr/bin/env python3
"""Offline labelled reference evaluation. No credentials, DB or provider calls."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.visibility.extraction import mentions, citation_rows


def evaluate():
    cases = json.loads(
        (ROOT / "backend/tests/fixtures/visibility/reference_cases.json").read_text()
    )
    entities = [
        {
            "id": "brand",
            "kind": "brand",
            "name": "Acme Balo",
            "config": {
                "aliases": [{"name": "Acme Bags"}, {"name": "Sen", "ambiguous": True}],
                "domains": [{"domain": "acme.test", "include_subdomains": False}],
            },
        },
        {
            "id": "competitor",
            "kind": "competitor",
            "name": "Beta Bags",
            "config": {
                "domains": [{"domain": "beta.test", "include_subdomains": False}]
            },
        },
    ]
    tp = fp = fn = tn = abstained = cite_tp = cite_fp = cite_fn = 0
    rows = []
    for case in cases:
        if "text" not in case:
            continue
        found = mentions(case["text"], entities)
        for entity in entities:
            matches = [m for m in found if m["entity_id"] == entity["id"]]
            if matches and all(
                m["status"] in ("POSSIBLE_MATCH", "NEEDS_REVIEW") for m in matches
            ):
                abstained += 1
                continue
            actual = any(m["status"] == "CONFIRMED_MATCH" for m in matches)
            expected = case[entity["id"]]
            tp += int(actual and expected)
            fp += int(actual and not expected)
            fn += int(not actual and expected)
            tn += int(not actual and not expected)
        entries = (
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
        citations, warnings = citation_rows(case["text"], entries, entities)
        actual = sum(
            c["attribution_status"] == "CONFIRMED_ATTRIBUTION" for c in citations
        )
        cite_tp += min(actual, case["citations"])
        cite_fp += max(0, actual - case["citations"])
        cite_fn += max(0, case["citations"] - actual)
        rows.append(
            {
                "id": case["id"],
                "case": case["case"],
                "citation_attribution_abstained": bool(warnings),
                "passed": actual == case["citations"],
            }
        )
    return {
        "reference_cases": len(cases),
        "text_examples": len(rows),
        "scenario_examples_verified_by_pytest": sum("scenario" in c for c in cases),
        "entity_decisions": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
            "ambiguous_abstained": abstained,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "citation_attribution": {
            "true_positives": cite_tp,
            "false_positives": cite_fp,
            "false_negatives": cite_fn,
            "abstained_examples": sum(
                r["citation_attribution_abstained"] for r in rows
            ),
        },
        "scope": "Small synthetic, manually labelled fixture set. Citation checks validate reported attribution only, not URL availability or claim support. Scenario assertions run separately in pytest. No production-wide accuracy claim.",
        "examples": rows,
    }


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert (
        result["entity_decisions"]["false_positives"]
        == result["entity_decisions"]["false_negatives"]
        == 0
    )
    assert (
        result["citation_attribution"]["false_positives"]
        == result["citation_attribution"]["false_negatives"]
        == 0
    )
