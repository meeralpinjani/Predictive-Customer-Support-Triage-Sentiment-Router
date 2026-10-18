# Integrity analyzer: evaluation

## Status: **not performed**

No accuracy, precision, recall or error rates are reported for the integrity analyzer, because there is **no real labelled data** to measure them on:

- The repository's labelled tickets (`backend/data/tickets_labelled.csv`, 384 rows) are synthetic and labelled for urgency and frustration, **not** for AI authorship, duplicates, consistency or manipulation.
- Generating "AI-written" and "human-written" tickets ourselves would measure our own generator, not real customers, so it would be misleading. **Synthetic results must never be presented as real-world reliability.**
- The model author's figure (0.997 validation accuracy) is on their own dataset (`rasbt/human-vs-ai-50k`), not on support tickets. See `MODEL_VERIFICATION.md`.

What *was* verified, by the automated tests in `backend/tests/test_integrity.py`, is **behaviour**, not accuracy:
- the label mapping and refusal rules
- chunking and aggregation
- timeouts, document limits and security
- duplicate, consistency and policy logic
- admin-only access
- the invariants that keep ticket handling unchanged

## Data needed for a real evaluation

| Requirement | Detail |
|---|---|
| Source | Real support tickets and attachments, collected **with consent** and stripped of personal data where possible |
| Labels | Per ticket: AI-assisted yes/no (self-reported or known), confirmed duplicate pairs, confirmed integrity concerns (from closed investigations), with who labelled them and how |
| Size | At least ~500 tickets per class for the AI signal; at least ~100 confirmed integrity concerns for the policy |
| Balance | Report class balance; don't oversample silently |
| Splits | **By source**: by customer, time period or channel, so near-identical texts never cross train/test. Thresholds tuned on a validation split only |
| Breakdowns | By language (English, Hinglish, Hindi, other), by text length (< 40, 40–200, > 200 words), by native vs non-native English where known, and by document type (typed text, PDF, DOCX) |

## Metrics to report (each with its sample size n)

- **AI signal:** precision, recall, false-positive rate (FPR), false-negative rate (FNR) and F1 at the review threshold. Report FPR on non-native English separately, since that is the main fairness risk.
- **Duplicates:** precision and recall of the near-identical flag, by method (MiniLM and TF-IDF).
- **Policy:** how many `review_recommended` cases reviewers confirmed vs dismissed.
- **Latency:** p50, p95 and p99 per assessment, by text length and number of documents.

## How to run it once data exists

Add a script under `backend/eval/` that reads the labelled file, splits by source, tunes thresholds on the validation part only, and writes a report next to `eval/report.json`. Until then, every threshold in `DECISIONS.md` stays **provisional**.
