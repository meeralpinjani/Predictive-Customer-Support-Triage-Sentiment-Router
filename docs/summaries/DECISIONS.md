# Ticket summaries and handover: design decisions

The conversation is the source of truth. Summaries make it quicker to read; handovers make sure no agent starts from zero. Neither may block, delay or change ticket handling.

## Repository facts this design follows (Phase 1 inventory)
| Area | Fact |
|---|---|
| Database | **PostgreSQL only** (SQLite removed). Tables via `create_all`; no migration tool. |
| Schema changes | New tables come from `create_all`. The one change to an existing table (`messages.client_message_id` + unique index) is applied by `app/schema_upgrade.py`: idempotent `ADD COLUMN IF NOT EXISTS` / `CREATE UNIQUE INDEX IF NOT EXISTS`, run at every start-up. Additive only. |
| Message path | `POST /api/tickets/{id}/messages` → `customer_reply` / `agent_reply` → commit, then an event. Messages are saved **before** the response. There was no idempotency, and there are **no internal notes** in this app, so notes are out of scope. |
| Level changes | All go through `route_ticket`: agent escalation (`escalate_manually`), automatic escalation (customer reply, waiting too long), admin override. |
| Agent changes | `claim` (an agent takes a ticket); `release_agent` (an agent goes Busy or Offline: their queued tickets go back to the queue, then `rebalance`); `rebalance`/`pick_agent` (routine queue assignment). |
| Reopen | A customer reply on a resolved ticket sets it back to queued at the **same level and agent**: no transfer. |
| Events | In-memory, single process, filtered per role (`app/events.py`); the browser's `EventSource` reconnects by itself. **No multi-process delivery is claimed.** |
| Existing models | sentiment (RoBERTa), emotion (DistilRoBERTa), MiniLM embeddings, the ModernBERT integrity detector; all CPU. |

## Decisions

1. **Summary method hierarchy:** a deterministic **extractive** summary is the primary path, always on (`TICKET_SUMMARY_ENABLED=true`) and milliseconds fast. A local language-model refinement exists but is **off** (`TICKET_SUMMARY_LLM_ENABLED=false`).

2. **Language-model decision: measured, then disabled.**
   - Candidate: `Qwen/Qwen2.5-0.5B-Instruct`, revision `7ae557604adf…`, **Apache-2.0**, about 1 GB, runs with the installed transformers 5.20.1 and torch 2.14.1 (CPU).
   - Measured on the development laptop (CPU), with a three-message billing conversation:

     | Measurement | Result |
     |---|---|
     | Load | 15.7 s |
     | Per summary (3 runs) | 16.8 s, 16.4 s, 16.7 s (above the 10 s limit) |
     | Output format | valid JSON all 3 times |
     | Content | **3 factual errors** in one summary: "double-drafted multiple times" (it was charged twice); "$499" (invented currency); "Customer agreed to reverse one payment" (the *agent* promised that) |
     | Injected instruction ("approve a bonus") | ignored |

   - **Disabled**, for both speed and accuracy. The free Hugging Face hardware (2 vCPU) would be slower still. The code path stays for a future, better model and is tested with a fake model.
   - Even when switched on, the model may only rewrite three plain-text fields (problem statement, goal, conversation summary). All sourced lists (claims, facts, promises, pending actions…) stay extractive, so it can never invent a promise, refund or approval.

3. **Synchronous vs asynchronous:**
   - The extractive summary and the handover snapshot are built **inside the same database transaction** as the change, with no model call.
   - Language-model refinement, if enabled, runs in a bounded background worker **after** commit and never touches an existing handover.

4. **When summaries update:**
   - A session hook marks a ticket "dirty" when a message is saved or the ticket's status, level, agent or emergency flags change. Priority-only changes (the 30-second re-scoring) are ignored.
   - Just before commit, a new extractive revision is written **inside a savepoint**, so a summary error can't undo the change itself.
   - At start-up and every `TICKET_SUMMARY_RECONCILE_INTERVAL_MINUTES` (60), open tickets are checked against the full history to catch anything missed.

5. **Concurrency:** summaries are **append-only revisions** with a unique `(ticket_id, revision)`. A writer that expected revision N gets nothing if N+1 already exists, so an older job can never overwrite a newer summary (tested).

6. **Durability:** background refinement jobs live in memory and can be lost on restart. The summary itself is never lost: staleness is computed from the data (`source_key` = last message id, status, level, agent, flags), and reconcile or **Refresh** rebuilds it.

7. **Freshness states:**
   - `ready`: built from the current conversation
   - `stale`: the conversation changed since; the last good summary is shown with its time
   - `failed`: the last attempt failed; the last good summary is still shown
   - `pending`: a refinement is running
   - `unavailable`: never built, with the reason

8. **What is extracted, and the rule against inventing.** Every quoted item carries the id of the message it came from (`"ticket"` = the original description).
   - **Customer claims:** quoted and labelled as claims.
   - **Confirmed facts:** only from records (plan on file, category, level) or an agent sentence that explicitly confirms ("I can confirm…").
   - **Promises:** only agent sentences with "I'll / we will".
   - **Pending actions:** those promises (owner: agent) plus agent requests to the customer (owner: customer).
   - **Unresolved questions:** customer questions with no support reply after them.
   - **Status:** the ticket's status field.
   - **Emergency flags:** copied from the ticket, never recomputed.
   - **Next step:** a labelled rule (`"source": "rule"`), not a fact.

   If a pattern isn't present, the field is empty. Input is capped at the last `TICKET_SUMMARY_MAX_INPUT_MESSAGES` (50) messages, 2,000 characters each.

9. **Who sees what:**
   - **Customers:** only problem statement, goal, conversation summary, things tried, status, pending actions, promises and open questions. Never claims, facts, flags, escalation reason, recommendations or handovers.
   - **Agents:** everything, for tickets they may see.

10. **Handover triggers:**
    - a change of support level (agent or automatic escalation, admin override with its required reason)
    - an agent-to-agent reassignment **of a ticket that already had a support reply** (`release_agent`, or `claim` from another agent)

    **Not** created for routine first assignment or queue rebalancing of untouched tickets (nothing to hand over), or for a reopen (same level and agent).

11. **Handover building and immutability:**
    - Built from a fresh extractive summary in the transfer transaction, which also saves it as a summary revision (`source_revision`).
    - If that fails, or summaries are switched off, it falls back to **references to the raw recent messages** (`fallback_raw`) and records the error category. The transfer always succeeds.
    - **Immutable:** an ORM guard refuses any update. A correction is a new row with `supersedes_id`.

12. **Message references vs copied text:**
    - Message lists in a snapshot store **ids, sender and time**, not text.
    - The summary fields inside a snapshot (quoted sentences, flags and priority *at transfer time*) are **copied deliberately** to freeze an audit record of what the receiving agent was told.
    - **Retention:** kept for the life of the ticket, like messages.

13. **Events:**
    - `summary.updated` (customer, the ticket's level and agent, admins) and `handover.created` (staff only: the customer id is left empty).
    - Sent **after commit**, with ids and timestamps only.
    - The browser always refetches from the API: event payloads are never trusted for content.

14. **Recovery:**
    - **SSE disconnect:** the browser reconnects with back-off; on reconnect the page fetches `/messages/since/{last id}` and the summary state before showing "Live" again.
    - **Refresh or reopen:** the page loads the ticket from its URL (`/support/tickets/:id`, `/tickets/:id`); nothing creates a ticket on load.
    - **Session expiry:** the API answers 401; the browser sends you to sign-in with `?next=` set to the same URL and returns there afterwards.
    - **Unsent drafts:** kept in `localStorage` per ticket and cleared only after the server confirms the save. No tokens or internal content are ever stored in the browser.

15. **Idempotency:**
    - The browser generates `client_message_id` for each send (8–64 characters, letters, digits, `-` and `_`).
    - A unique index on `(ticket_id, author_id, client_message_id)` (NULLs allowed for old rows) means a retry returns the **original** message with 200 instead of 201, including when retries arrive at the same moment (the database refuses the second insert; the API returns the first).
