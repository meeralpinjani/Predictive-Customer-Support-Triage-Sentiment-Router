# Integrity analyzer: design decisions

Written before the feature code. Each decision states the conservative choice and why.

## Scope
An **integrity review aid for administrators**. It never decides fraud, never changes priority, reply-by time (SLA), routing level, emergency flags or agent assignment, never hides a ticket and never blocks a customer. Admins see everything; **agents see only two yes/no hints** on queue cards and the ticket page ("AI-like writing", "review suggested"), with no score, evidence or actions; customers see nothing. (Agent hints added on request, 2026-10-18.)

## Repository facts this design follows (Phase 1)
| Area | Fact |
|---|---|
| Schema | SQLAlchemy 2 models in `app/models.py`, integer autoincrement keys, timestamps via `UTCDateTime` in `app/db.py`, JSON stored as `Text` (e.g. `explanation_json`). |
| Migrations | **No migration tool.** Tables are created by `Base.metadata.create_all` at start-up (`app/main.py`) and by `scripts/seed.py`. New tables are created automatically; existing tables can't be altered this way. → The feature adds **two new tables only** and changes no existing table. No Alembic (the brief forbids adding a tool not in use). |
| Model loading | `app/nlp/hf.py`: lazy `lru_cache` singletons, background warm-up, status flags, `ThreadPoolExecutor` + `result(timeout=…)` in `analyzer.py`. The detector follows the same pattern. |
| Events | `app/events.py`: typed events (`type` field), per-role filter `_wants`; admins receive everything; customers only events with their `customer_id`; agents events with their level or assignment. |
| Auth | `current_user`, `require(*roles)`; roles `customer`, `level1`–`level3`, `admin`; object checks `can_view` / `_viewable` in `app/api/tickets.py`. |
| Attachments | `app/services/files.py`: magic-byte check, stored in the database (`attachments.content`). |
| Language | `app/nlp/rules.detect_language` already returns `en`, `hi-en` (Hinglish) or `hi` (Devanagari). |

## Decisions

1. **Where the classifier runs: in-process**, lazily loaded singleton behind a lock (same pattern as `hf.py`). A separate worker process would be safer for memory but adds a deployment piece the app doesn't have.
2. **Concurrency:** one inference at a time, behind a `threading.Lock`, run in a **bounded `ThreadPoolExecutor(max_workers=1)`**.
3. **Timeout:** `future.result(timeout=AI_INTEGRITY_TIMEOUT_SECONDS)`. A CPU-bound call **can't be killed in-process**: the caller stops waiting, the assessment records `model_unavailable / timeout`, and the late result is discarded.
4. **Async processing:** after the ticket or reply is **committed**, a `pending` assessment row is written and its id is put on a **bounded in-memory queue** (max 200) served by **one daemon worker thread**. Not FastAPI `BackgroundTasks`.
   - **Durability:** the queue is lost on restart. At start-up, rows still `pending` are re-queued; anything else can be re-run with the **reassess** endpoint. Not guaranteed exactly-once.
   - If the queue is full, the row stays `pending` (re-queued at the next start-up or by reassess). Ticket creation is never delayed.
5. **Deduplication:** each trigger has a unique `trigger_key` (`ticket:<id>:created`, `message:<id>`, `attachments:<ids>`, `manual:<random>`). A unique constraint makes retries no-ops.
6. **What is assessed:** the customer-written text of the ticket (subject, description and every customer message) plus text extracted from customer-uploaded PDF/DOCX attachments (scored separately per document). Agent messages are never assessed; they aren't customer content.
7. **Score semantics:** the detector returns the temperature-scaled softmax value of its **verified AI class**. The API and UI call it a **"detector score (not a probability)"**. No calibration claim is made for our tickets (no real labelled data; see `EVALUATION.md`).
8. **Chunking:** tokenizer windows of `AI_INTEGRITY_CHUNK_SIZE` tokens (default 512, must be ≤ model max length − 2) with `AI_INTEGRITY_CHUNK_OVERLAP` (default 64), at most `AI_INTEGRITY_MAX_CHUNKS` (16) to bound CPU time; extra text is reported as a limitation. **Mean and max** are both stored; the **mean** drives the policy.
9. **Language:** reuse `detect_language`: `hi` and `hi-en` → `unsupported_language`. Text whose letters are less than 80% basic Latin is also `unsupported_language` (the model card says English only). **No new language-detection dependency.**
10. **Minimum length:** fewer than `AI_INTEGRITY_MIN_WORDS` (provisional 40) words → `insufficient_text`. Detectors are unreliable on short text, and most tickets are short.
11. **Document extraction:**
    - **PDF:** `pypdf` 6.21.1 (pure Python, no native code; the only new dependency).
    - **DOCX:** Python's own `zipfile` + `xml.etree`, no new dependency. Bounded: entry count, total uncompressed size, compression ratio (zip-bomb guard); documents with a `<!DOCTYPE` are refused (entity attacks); macros and embedded objects are never opened.
    - Everything is parsed **in memory from the bytes already stored in the database**, so no temporary files are written at all, and therefore none can leak. Limits come from configuration: size, pages, characters, timeout.
    - Image-only or near-empty PDFs → `needs_ocr` ("could not be fully analysed"); no OCR.
    - DOCX becomes an allowed attachment type (magic bytes `PK` + `[Content_Types].xml` + `word/document.xml`).
12. **Duplicates:** reuse `services/similarity.similarity_matrix` (MiniLM when loaded, TF-IDF otherwise). Candidates: tickets from the last `AI_INTEGRITY_DUPLICATE_WINDOW_DAYS` (30), at most 300, **excluding the current ticket**, filtered by `can_view(viewer, ticket)`. The background job uses the admin view (admins can see every ticket). Thresholds differ by method because the scales differ: MiniLM `AI_INTEGRITY_DUPLICATE_THRESHOLD` (provisional 0.90), TF-IDF `AI_INTEGRITY_DUPLICATE_THRESHOLD_TFIDF` (provisional 0.80). Matches sharing the ticket's incident, or where both tickets are outages, count as a **shared issue**, not a concern.
13. **Evidence consistency:** only against records this app owns.

    | Claim in the text | Source | Result |
    |---|---|---|
    | "first time contacting / never contacted you" | ticket history | prior tickets exist → `verified_conflict` |
    | "3rd time / contacted you many times" | ticket history | no prior tickets → `possible_inconsistency` (could be another channel) |
    | names a plan ("enterprise plan") | customer record | differs from the plan on file → `possible_inconsistency` |
    | money claims (charged, refund, payment) | **no payment records exist here** | `insufficient_evidence` |

    The overall status is the strongest finding; with no checkable claim it's `no_conflict_detected`. No outside verification source is invented.
14. **Manipulation indicators:** deterministic, each with a documented threshold.
    - `repeat_near_identical_submission`: ≥ 1 other ticket from the **same customer** above the duplicate threshold within `AI_INTEGRITY_REPEAT_WINDOW_HOURS` (24).
    - `review_bypass_requests`: ≥ `AI_INTEGRITY_BYPASS_MIN_REQUESTS` (2) phrases asking to skip or bypass checks, verification or review.
    - `instructions_aimed_at_automation`: any phrase addressing an automated system ("ignore previous instructions", "system prompt", "as an AI…").

    Never flagged: capitals, anger, urgency, formality, grammar, non-native English, AI or translation use.
15. **Policy (version `2026-10-18.1`), no combined numeric score.** Reasons:
    - `verified_conflict`
    - any manipulation indicator
    - cross-customer near-identical text that isn't a shared issue
    - `ai_pattern` (assessed, mean ≥ `AI_INTEGRITY_REVIEW_THRESHOLD`, provisional 0.80)
    - `possible_inconsistency`
    - document `needs_ocr`

    Mapping:
    - `review_recommended` if a **strong** reason exists (conflict, indicator, cross-customer duplicate), or **two or more weak** reasons (AI pattern, possible inconsistency).
    - **AI patterns alone never recommend review**; the UI shows them as "AI-like writing patterns detected (not evidence on its own)". This is the conservative reading, because AI and translation help are legitimate.
    - Otherwise `clear`.
    - `under_review`, `confirmed_integrity_concern` and `dismissed` are set only by admin actions.
    - On reassessment, `under_review` and `confirmed` carry forward. `dismissed` carries forward unless a reason appears that the dismissed assessment didn't have.
16. **Append-only:** reassessment always inserts a new row; review actions reference the exact assessment they acted on; nothing is updated except a pending row filling in its result.
17. **Events:** `integrity.assessed`, `integrity.review_updated`, sent **after commit** with ids and states only. `customer_id`, `route` and `assigned_agent_id` are left empty, so `_wants` delivers them to admins only.
18. **Switch:** `AI_INTEGRITY_ENABLED=false` by default. When off, no rows are written, no job runs, and ticket behaviour is identical to before.
19. **Model path:** only from configuration (`AI_INTEGRITY_MODEL_PATH`, a local directory), validated at start-up; never from a request. No external AI API is ever called.
20. **Provisional values:** `AI_INTEGRITY_MIN_WORDS`, `AI_INTEGRITY_REVIEW_THRESHOLD`, both duplicate thresholds and the indicator thresholds are **provisional**: not validated, because there's no real labelled data.
