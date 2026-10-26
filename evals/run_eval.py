"""Release gate for a prompt change.

Usage:
    python -m evals.run_eval --candidate data/outputs_prompt_v2.json

Fails (exit code 1) if the candidate drops below the thresholds or is worse
than the approved baseline, so a CI pipeline blocks the change.
"""
import argparse
import json
import sys
from pathlib import Path

from evals.metrics import evaluate

ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = {"precision": 0.95, "recall": 0.90, "fabricated_summaries": 0}


def load(path):
    return json.loads(Path(path).read_text())


def gate(candidate, baseline):
    problems = []
    if candidate["precision"] < THRESHOLDS["precision"]:
        problems.append(f"precision {candidate['precision']} < {THRESHOLDS['precision']}")
    if candidate["recall"] < THRESHOLDS["recall"]:
        problems.append(f"recall {candidate['recall']} < {THRESHOLDS['recall']}")
    if candidate["fabricated_summaries"] > THRESHOLDS["fabricated_summaries"]:
        problems.append(f"{candidate['fabricated_summaries']} summary(ies) contain untraceable numbers")
    for m in ("precision", "recall"):
        if candidate[m] < baseline[m]:
            problems.append(f"{m} regressed: {baseline[m]} -> {candidate[m]}")
    return problems


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--golden", default=ROOT / "data/golden_set.json")
    p.add_argument("--baseline", default=ROOT / "data/outputs_prompt_v1.json")
    p.add_argument("--candidate", default=ROOT / "data/outputs_prompt_v1.json")
    p.add_argument("--report", default=ROOT / "eval_report.json")
    a = p.parse_args(argv)

    golden = load(a.golden)
    base = evaluate(golden, load(a.baseline))
    cand = evaluate(golden, load(a.candidate))
    problems = gate(cand, base)

    Path(a.report).write_text(json.dumps({"baseline": base, "candidate": cand, "problems": problems}, indent=2))
    print(f"Baseline : precision={base['precision']} recall={base['recall']}")
    print(f"Candidate: precision={cand['precision']} recall={cand['recall']} "
          f"fabricated_summaries={cand['fabricated_summaries']}")
    for f in cand["failures"]:
        print("  -", f)
    if problems:
        print("\nBLOCKED:\n  " + "\n  ".join(problems))
        return 1
    print("\nPASSED release gate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
