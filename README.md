# AI-Enabled QA Portfolio

![QA checks](https://github.com/HilinaTesfaye7/ai-qa-portfolio/actions/workflows/qa.yml/badge.svg)

A small QA project that tests an AI-assisted acquisitions tool: document extraction,
deal data, and an approval tracker. The app is a deliberately simple mock; **the tests
are the point**. Everything runs automatically on every push through GitHub Actions.

## What it covers

| Area | What is tested | Where |
| --- | --- | --- |
| AI output evaluation | Golden set of 6 historical cases, field-level precision and recall, regression gate after a prompt change | `evals/`, `tests/test_ai_eval.py` |
| Fabricated facts | Every number in an AI summary must appear in the source document | `evals/metrics.py` |
| Document edge cases | Scanned/OCR noise, rotated page, missing signature, net loss, missing field | `data/golden_set.json` |
| SQL data validation | Row counts, duplicate uploads, orphaned records, totals that don't reconcile, data rooms that look complete but aren't | `app/data_checks.py`, `tests/test_data_integrity.py` |
| API testing (pytest) | Status codes, payload structure, auth failures, invalid input, repeated identical requests | `tests/test_api.py` |
| UI testing (Playwright) | Approval step: submit blocked until review, including a forced bypass attempt | `tests/test_ui_approval.py` |
| CI pipeline | GitHub Actions runs all tests and the AI release gate on every push | `.github/workflows/qa.yml` |

## The AI release gate

`data/outputs_prompt_v1.json` is the approved baseline. `data/outputs_prompt_v2.json`
simulates a prompt change that looks fine at a glance but fails confidently:

- reports a **net loss as a profit** (sign error)
- says an **unsigned statement is signed**
- **invents a revenue figure** for a document that has none, and repeats it in the summary

```
python -m evals.run_eval --candidate data/outputs_prompt_v2.json
```

```
Baseline : precision=1.0 recall=0.963
Candidate: precision=0.889 recall=0.889 fabricated_summaries=1
BLOCKED:
  precision 0.889 < 0.95
  recall 0.889 < 0.9
  1 summary(ies) contain untraceable numbers
  precision regressed: 1.0 -> 0.889
  recall regressed: 0.963 -> 0.889
```

**Precision** answers "when the model states a value, how often is it right?"
**Recall** answers "of the values in the documents, how many did it find?"
A wrong value counts against both; an invented value counts against precision.

## Data checks prove they work

Each SQL check runs on clean data (must find nothing) and on data with planted defects
(must find exactly those defects). A check that has never been seen to fail isn't trusted.

## Run it locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium

pytest                             # all tests
pytest -m "not ui"                 # API, SQL and AI tests only
python -m evals.run_eval           # release gate on the baseline (passes)
python -m evals.run_eval --candidate data/outputs_prompt_v2.json   # blocked
```

## Structure

```
app/        mock service, database seed, SQL checks
data/       golden set and two versions of AI output
evals/      precision/recall, fabrication check, release gate
tests/      pytest + Playwright suites
.github/    CI pipeline
```
