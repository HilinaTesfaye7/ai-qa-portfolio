"""AI output tests: golden set, precision/recall, regression after a prompt change,
and fabricated-fact checks."""
import json
from pathlib import Path

import pytest

from evals.metrics import evaluate, fabricated_numbers, score_fields
from evals.run_eval import THRESHOLDS, gate

DATA = Path(__file__).resolve().parent.parent / "data"
GOLDEN = json.loads((DATA / "golden_set.json").read_text())
V1 = json.loads((DATA / "outputs_prompt_v1.json").read_text())
V2 = json.loads((DATA / "outputs_prompt_v2.json").read_text())


# ---- the metric itself must be right before we trust it ----

def test_precision_recall_counts_on_a_known_example():
    expected = {"revenue": 100, "net_income": None, "signed": True}
    predicted = {"revenue": 100, "net_income": 5, "signed": False}
    tp, fp, fn, _ = score_fields(expected, predicted)
    # revenue correct; net_income invented (FP); signed wrong (FP + FN)
    assert (tp, fp, fn) == (1, 2, 1)


@pytest.mark.parametrize("summary, source, expected", [
    ("Revenue was 1,200,000.", "Total revenue 1,200,000.", []),
    ("Revenue was 1,250,000.", "Total revenue 1,200,000.", [1250000.0]),
    ("A net loss of 58,000.", "Net loss (58,000).", []),
    ("No numbers here.", "Revenue 5.", []),
])
def test_fabricated_number_detection(summary, source, expected):
    assert fabricated_numbers(summary, source) == expected


# ---- the approved baseline meets the bar ----

def test_baseline_meets_thresholds():
    r = evaluate(GOLDEN, V1)
    assert r["precision"] >= THRESHOLDS["precision"]
    assert r["recall"] >= THRESHOLDS["recall"]
    assert r["fabricated_summaries"] == 0


@pytest.mark.parametrize("case", GOLDEN, ids=lambda c: f"{c['case_id']} {c['scenario']}")
def test_every_summary_number_is_traceable_to_source(case):
    out = next(o for o in V1 if o["case_id"] == case["case_id"])
    assert fabricated_numbers(out["summary"], case["source_text"]) == []


# ---- a bad prompt change is caught ----

def test_regression_gate_blocks_worse_prompt():
    problems = gate(evaluate(GOLDEN, V2), evaluate(GOLDEN, V1))
    assert any("precision regressed" in p for p in problems)
    assert any("untraceable numbers" in p for p in problems)


def test_regression_gate_catches_specific_edge_cases():
    failures = evaluate(GOLDEN, V2)["failures"]
    caught = {(f["case_id"], f.get("field") or f.get("problem")) for f in failures}
    assert ("GS-004", "signed") in caught          # missing signature reported as signed
    assert ("GS-005", "net_income") in caught      # net loss reported as profit
    assert ("GS-006", "revenue") in caught         # revenue invented when the document has none
