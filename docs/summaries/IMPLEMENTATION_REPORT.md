# Summaries, handover and recovery: implementation report (2026-10-18)

Everything below was observed in a real run.

## Gates
| Gate | Result |
|---|---|
| 1 Inspection | Inventory in `DECISIONS.md`. Baseline after the SQLite removal: **159 passed, 0 failed** (PostgreSQL, throwaway schema). Two items in the brief don't exist in this app: internal notes and a separate agent-to-agent reassign endpoint. Recorded; nothing invented. |
| 2 Design | `DECISIONS.md`. Language model **measured, then disabled**: 15.7 s load, 16.4–16.8 s per summary on CPU (above the 10 s limit), 3 factual errors in one summary. |
| 3 Data model | Upgrade run first on a **copy** of the working database (13 tables, all row counts unchanged, new column + unique index + 2 new tables, second run a no-op), then applied to the working database at start-up. Fresh databases: every test run creates one. |
| 4 Summaries | Extractive tests pass; language-model path tested with a fake model (invalid output discarded, partial output limited to allowed fields, timeout keeps the last good summary, an older revision can't overwrite). The real model was run once for the measurement. |
| 5 Handover | Level 1→2 and 2→3 escalations, admin override and reassignment each create one handover in the transfer transaction; a summary failure falls back to `fallback_raw`; updates are refused; priority, reply-by time, flags and route lock unchanged. |
| 6 Recovery | Missed messages, resume (no new ticket), session expiry then resume, duplicate retry (201 then 200, one row), 4 simultaneous retries (one row). |
| 7 Frontend | `npm run build` succeeds (no frontend unit tests exist in this project). Browser checks below. |
| 8 Testing | **187 passed, 0 failed, 0 skipped** (159 existing + 28 new). |

## Bugs found and fixed while building
- The "about to commit" hook ran before pending changes were written, so plain replies didn't refresh the summary. Caught by a test; fixed by writing pending changes first.
- The upgrade helper didn't load the table definitions when run on its own, so new tables were missing on an existing database. Caught by the copy test; fixed.
- The real language model failed (the chat template returns a dictionary in transformers 5). Caught only by the real-model measurement; fixed.
- **"Remember me" on sign-in was ignored** (the login helper didn't pass it on). Fixed.
- Record-based facts were labelled as coming from the "original description". Fixed (now "ticket record").

## Files
| File | Purpose |
|---|---|
| `backend/app/services/summarization.py` | Extractive summaries, revisions, freshness, automatic updates via session hooks, reconcile |
| `backend/app/services/summary_llm.py` | Optional local model refinement (off), output validation, background worker |
| `backend/app/services/handover.py` | Snapshots in the transfer transaction, raw fallback, immutability guard |
| `backend/app/api/conversation.py` | Summary, freshness, refresh, missed messages, resume, handover endpoints |
| `backend/app/schema_upgrade.py` | Additive upgrade for existing PostgreSQL databases |
| `backend/app/models.py` | + `TicketSummary`, `Handover`, `Message.client_message_id` + unique index |
| `backend/app/services/triage.py`, `app/api/tickets.py` | Handovers on level changes, reassignment and claims; idempotent message sends; cursor paging |
| `backend/app/main.py`, `config.py`, `.env.example` | Hooks, start-up and periodic reconcile, `TICKET_SUMMARY_*` settings |
| `backend/tests/test_summaries.py` | 28 tests |
| `frontend/src/components/Summary.jsx` | View summary dialog, handover panel |
| `frontend/src/components/Conversation.jsx` | Drafts, Sending / Not sent / Retry, Resume conversation |
| `frontend/src/lib/events.jsx`, `lib/auth.jsx`, `App.jsx`, `api.js`, `pages/auth/AuthPages.jsx` | Connection states with back-off and catch-up, session expiry → back to the same page, new API calls |
| ticket pages and lists | Summary buttons on cards and ticket pages; handover panel above the reply box |

## Commands run
```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q          # 187 passed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000 --timeout-graceful-shutdown 3
cd ..\frontend; npm run build                    # built
```
Turning summaries off: `TICKET_SUMMARY_ENABLED=false` in `backend/.env`, then restart. Messages, routing and handovers keep working (tested).

## Browser verification (local PostgreSQL)
| Check | Observed |
|---|---|
| Same message sent twice with one id | 201 then 200, same message id (50) |
| Customer opens **View summary** | "Up to date", every quote names its source, no agent-only sections |
| Level 1 reply ("I can confirm… I will ask our technical team…") and **Escalate**; Level 2 opens the ticket | Handover box above the reply field: Level 1 (Astrid) → Level 2 (Ingrid), reason, tried, confirmed, still to do, promise, suggested next step |
| Draft typed, page refreshed | text still in the reply box |
| Network made to refuse the send | bubble "Not sent: Cannot reach the server… Retry"; draft kept |
| Network restored, **Retry** | 1 copy saved; draft cleared after confirmation |
| Session ended in the background, then a click | sign-in page "Your session expired", URL `/login?next=/tickets/48`; signing in returned to `/tickets/48` |
| Admin menu | groups Daily work / Reports / Tools & settings; Insights "Technical details" and Overview "Demo & testing tools" collapsed |

## Known limits
- **Live events are in memory, single process:** events sent while a browser is disconnected aren't replayed. Pages re-fetch from the API on reconnect instead.
- **Background refinement jobs aren't durable.** Summaries themselves are rebuilt from data at any time.
- **The language model stays off;** a stronger model or a GPU would be needed.
- **Not run:** the Docker image and the Hugging Face deployment (no Docker on this laptop).
