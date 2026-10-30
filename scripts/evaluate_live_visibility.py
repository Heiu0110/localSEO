#!/usr/bin/env python3
"""Evaluate labelled provider-shaped fixtures offline; never calls a provider or DB."""
import json
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.visibility.live_parser import parse_response


def evaluate():
    dataset = json.loads(
        (
            ROOT / "backend/tests/fixtures/visibility/live_reference_cases.json"
        ).read_text()
    )
    tp = fp = fn = abstained = eligible = 0
    results = []
    for case in dataset["cases"]:
        e = case["expected"]
        parsed = None
        try:
            parsed = parse_response(
                case["response"],
                "evaluation-request",
                "evaluation-prompt",
                "Original neutral question",
                {},
                "fixture-model",
            )
        except (ValueError, TypeError):
            if not e["parse_error"]:
                raise
        if e["parse_error"]:
            passed = parsed is None
            abstained += 1
        else:
            actual = (
                Counter(c.url for c in parsed["candidate"].citations)
                if parsed["candidate"]
                else Counter()
            )
            expected = Counter(e["citation_urls"])
            tp += sum((actual & expected).values())
            fp += sum((actual - expected).values())
            fn += sum((expected - actual).values())
            passed = (
                actual == expected
                and parsed["eligible"] == e["eligible"]
                and parsed["search_execution"] == e["search_execution"]
                and parsed["source_count"] == e["source_count"]
            )
            if parsed["candidate"]:
                passed &= (
                    parsed["candidate"].citation_metadata == e["citation_metadata"]
                )
            eligible += int(parsed["eligible"] and e["citation_metadata"] == "complete")
            abstained += int(
                not parsed["eligible"] or e["citation_metadata"] == "partial"
            )
        results.append({"id": case["id"], "name": case["name"], "passed": bool(passed)})
    return {
        "fixture_count": len(results),
        "eligible_complete_citation_samples": eligible,
        "citation_true_positives": tp,
        "citation_false_positives": fp,
        "citation_false_negatives": fn,
        "citation_precision": tp / (tp + fp) if tp + fp else None,
        "citation_recall": tp / (tp + fn) if tp + fn else None,
        "ineligible_or_partial_or_quarantined_examples": abstained,
        "span_mapping": "Not verified; separate references, no guessed inline highlight.",
        "source": dataset["source"],
        "production_accuracy_claim": False,
        "live_provider_verified": False,
        "results": results,
    }


if __name__ == "__main__":
    result = evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert all(row["passed"] for row in result["results"])
    assert result["citation_false_positives"] == result["citation_false_negatives"] == 0
