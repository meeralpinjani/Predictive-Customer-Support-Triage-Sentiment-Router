# Integrity analyzer: implementation report (2026-10-18)

Every result below was observed in a real run. Nothing is estimated.

## Gates

| Gate | Result |
|---|---|
| 1 Inspection | Inventory in `DECISIONS.md` ("Repository facts"). Baseline suite: **116 passed, 0 failed** (SQLite). |
| 2 Model verification | `MODEL_VERIFICATION.md`. Apache-2.0; `id2label {"0":"HUMAN","1":"AI"}`, cross-checked with `detector-config.json`; loaded in 2.02 s; **real backend** chosen. |
| 3 Design | `DECISIONS.md`, written before the feature code. |
| 4 Backend | Imports and starts; new tables created by `create_all` on SQLite and PostgreSQL; existing suite still **116 passed**. |
| 5 Testing | **159 passed, 0 failed, 0 skipped** on SQLite; **159 passed** on PostgreSQL 18; **159 passed** with `AI_INTEGRITY_ENABLED=true` (real background worker). |
| 6 Evaluation | **Not performed:** no real labelled data. See `EVALUATION.md`. |
| 7 Frontend | `npm run build` succeeded (395 kB JS, 113 kB gzipped; there are no frontend unit tests). Browser checks in the next section. |
| 8 Docs | `TEAM-GUIDE.md`, `HOW-TO-RUN-AND-TEST.md`, `DEPLOYMENT.md`, `TECHNICAL-DEEP-DIVE.md`, README and this folder are updated. |

## Architecture (short)
1. A ticket, customer reply or customer upload is committed.
2. `integrity.schedule()` writes a `pending` row (deduplicated by `trigger_key`) and queues it.
3. A single daemon worker runs `run_assessment()`, which computes four independent signals: detector, duplicates, records, indicators.
4. A versioned rule set produces a review state; the row is saved, then an admin-only event is published.

Admin review actions are audited in `integrity_review_actions`. Tickets are never modified.

## Files

| File | Purpose |
|---|---|
| `backend/app/nlp/ai_authorship.py` | Detector: lazy singleton, label verification, token windows, mean/max, lock and timeout, stub when unavailable |
| `backend/app/nlp/document_extractor.py` | PDF (pypdf) and DOCX (standard library) text extraction in memory, with limits |
| `backend/app/services/integrity.py` | Signals, policy, scheduling, background worker, review actions |
| `backend/app/api/integrity.py` | Admin-only API |
| `backend/app/models.py` | + `IntegrityAssessment`, `IntegrityReviewAction` (new tables only) |
| `backend/app/config.py` | + `AI_INTEGRITY_*` settings (off by default; provisional values marked) |
| `backend/app/main.py` | Registers the router; starts/stops the worker; re-queues pending rows at start-up |
| `backend/app/api/tickets.py` | Schedules assessments **after commit** for ticket creation, customer replies and customer uploads |
| `backend/app/services/files.py` | DOCX becomes an allowed attachment (checked by real content) |
| `backend/scripts/download_integrity_model.py` | Pinned download plus label check |
| `backend/tests/test_integrity.py` | 43 tests |
| `backend/requirements.txt` | + `pypdf==6.21.1` (the only new package) |
| `backend/Dockerfile`, `backend/.env.example` | Model baked into the image; settings documented |
| `frontend/src/pages/admin/IntegrityPage.jsx` | Integrity page: queue, filters, detail, actions, dialogs |
| `frontend/src/api.js`, `App.jsx`, `components/layout/AppShell.jsx`, `lib/events.jsx`, `components/Attachments.jsx` | API calls, route, nav item, event types, DOCX upload |

## Migration
There's no migration tool in this project. New tables are created at backend start-up (`Base.metadata.create_all`).

Observed on the local PostgreSQL after restarting the backend:
```
postgresql ['integrity_assessments', 'integrity_review_actions']
integrity_assessments 28 columns
integrity_review_actions 6 columns
```
No existing table was changed.

## Commands (all run during this work)
```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.download_integrity_model
#   -> "Downloaded rasbt/ai-text-detector-modernbert@a6efd4bf6ecd ... (AI class index 1)"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
.\.venv\Scripts\python.exe -m pytest -q          # 159 passed
cd ..\frontend; npm run build                    # built
```

## Endpoints (all admin-only; 403 for customers and agents, tested)
- `GET /api/integrity/status`
- `GET /api/integrity/assessments`
  - filters: `review_state`, `ai_status`, `has_duplicates`, `date_from`, `date_to`, `q`
  - `sort`, `page`, `page_size`
  - stats are computed from the database
- `GET /api/integrity/assessments/{id}`
- `GET /api/integrity/assessments/{id}/related`
- `GET /api/integrity/assessments/{id}/history`
- `POST /api/integrity/assessments/{id}/review`: `{action: start_review|dismiss|confirm, reason}`; a reason is required for confirm; unknown fields are rejected; body limited to 4 KB
- `GET /api/integrity/tickets/{ticket_id}/assessments`
- `POST /api/integrity/tickets/{ticket_id}/reassess`: returns 202; rate-limited per ticket

## Browser verification (local PostgreSQL, real detector)
Four tickets were created through the website's API.

| Ticket | Observed |
|---|---|
| #44 "first time contacting" (customer has 2 earlier tickets) + two "skip the verification / skip the review" | **Review suggested**: "Conflicts with our records" plus the "review bypass requests" indicator. Detector score 0.0004 (no AI pattern). |
| #45 and #46: near-identical text from the same customer | **Review suggested**: repeat-submission indicator, 1 near-identical ticket each |
| #47 Hinglish payment ticket | **Clear**, "Language not supported (English only)", payments "Can't be checked here" |

On the page:
- Summary counts were correct.
- Opening #44 showed every section.
- **Start review**, then **Confirm concern**: the button stays disabled until a reason of at least 10 characters is typed; once confirmed, the counts updated live and **History** listed both actions with the admin's name, time and reason.
- The ticket's handling stayed at **Level 1, priority 43** throughout.
- No sideways page scroll at desktop width (1009 px) or phone width (375 px); no console errors.

## Blockers and remaining work
- **Not evaluated on real data:** every threshold is provisional (see `EVALUATION.md`).
- **The job queue is in memory:** pending rows are re-queued at start-up; anything else needs **Reassess**.
- **No OCR:** scanned documents are reported as "could not be fully analysed".
- **English-only detector:** Hinglish and Hindi tickets get no writing check.
- The Docker image grows by about 300 MB for the detector. The Docker build itself wasn't run on this laptop (Docker isn't installed).
