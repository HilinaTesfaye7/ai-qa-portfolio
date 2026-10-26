"""Evaluation helpers for AI extraction output.

Field-level scoring against a golden set of historical cases:
- True positive (TP):  the model gave a value and it matches the expected value.
- False positive (FP): the model gave a value that is wrong, or gave a value
                       where the document has none (a fabricated field).
- False negative (FN): the document has a value and the model missed it or got it wrong.

Precision = TP / (TP + FP)  -> "when the model says something, how often is it right?"
Recall    = TP / (TP + FN)  -> "of the facts in the documents, how many did it find?"
"""
import re

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def score_fields(expected, predicted):
    tp = fp = fn = 0
    errors = []
    for field, exp in expected.items():
        got = predicted.get(field)
        if exp is None and got is None:
            continue
        if exp is not None and got == exp:
            tp += 1
            continue
        if got is not None:
            fp += 1
        if exp is not None:
            fn += 1
        errors.append({"field": field, "expected": exp, "got": got})
    return tp, fp, fn, errors


def numbers_in(text):
    """All numbers in a text, normalised (commas removed)."""
    return {float(m.replace(",", "")) for m in NUMBER.findall(text)}


def fabricated_numbers(summary, source_text):
    """Numbers stated in a summary that cannot be traced to the source document."""
    source = numbers_in(source_text)
    return sorted(n for n in numbers_in(summary) if n not in source)


def evaluate(golden, outputs):
    by_id = {o["case_id"]: o for o in outputs}
    TP = FP = FN = 0
    failures = []
    for case in golden:
        out = by_id.get(case["case_id"])
        if out is None:
            failures.append({"case_id": case["case_id"], "problem": "no output for case"})
            FN += sum(v is not None for v in case["expected"].values())
            continue
        tp, fp, fn, errors = score_fields(case["expected"], out["fields"])
        TP, FP, FN = TP + tp, FP + fp, FN + fn
        for e in errors:
            failures.append({"case_id": case["case_id"], "scenario": case["scenario"], **e})
        fake = fabricated_numbers(out["summary"], case["source_text"])
        if fake:
            failures.append({"case_id": case["case_id"], "scenario": case["scenario"],
                             "problem": "summary contains numbers not found in source", "numbers": fake})
    precision = TP / (TP + FP) if TP + FP else 0.0
    recall = TP / (TP + FN) if TP + FN else 0.0
    fabrications = [f for f in failures if f.get("problem", "").startswith("summary contains")]
    return {"precision": round(precision, 3), "recall": round(recall, 3),
            "tp": TP, "fp": FP, "fn": FN,
            "fabricated_summaries": len(fabrications), "failures": failures}
