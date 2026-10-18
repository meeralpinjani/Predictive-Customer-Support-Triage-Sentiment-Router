# Ticket summaries, handovers and recovery

Why each choice was made, plus the measured AI evidence: [DECISIONS.md](DECISIONS.md). Results of building it: [IMPLEMENTATION_REPORT.md](IMPLEMENTATION_REPORT.md).

## What it is, and what it isn't
- **Summary:** a quick read of a ticket, built only from saved messages and ticket fields. Every quoted line names its source message. It's a convenience: **the full conversation is always the source of truth** and always one click away.
- **Handover:** a frozen snapshot written at the moment a ticket moves to another level or agent, so the next person doesn't start from zero.
- **Neither changes ticket handling:** priority, reply-by time, emergency flags, route locks, level and assignment are untouched (tested).

## Freshness states
| State | Meaning | What you see |
|---|---|---|
| ready | built from the current conversation | "Up to date" |
| stale | the conversation changed since | "Out of date", with the last good summary and its time |
| pending | an optional AI refinement is running | "Updating…" |
| failed | the last update failed | "Last update failed", with the last good summary |
| unavailable | never built | "Not available", with the reason |

## Recovery flow
```
connection lost ──► sidebar "Reconnecting…" / "Offline"; chat shows "Resume conversation"
      │               (messages already sent are saved; new ones wait as "Not sent – Retry")
      ▼
browser reconnects (1 s, 2 s, 4 s … up to 30 s; at once when the network comes back)
      ▼
"Catching up…": every page re-fetches from the API (messages, summary, handovers), because live
events sent while disconnected are not replayed (the event bus is in memory, single process)
      ▼
"Live" again

refresh / reopen ─► the page loads the ticket from its URL; nothing ever creates a ticket on load
session expired  ─► any request answers 401 → sign-in page "Your session expired" with ?next=<page>
                    → after signing in, straight back to the same ticket
```

## Sending messages safely
- The browser gives each message a random `client_message_id`. The server keeps one message per `(ticket, author, client_message_id)`; a retry returns the **original** message (HTTP 200) instead of saving a copy, even if two retries arrive at once.
- A message is only shown as saved once the server returned it: *Sending…*, then saved; or *Not sent – Retry*, which retries with the same id.
- Unsent text is kept in the browser per ticket (`localStorage`) and cleared only after the server confirms. Nothing secret is stored there: no passwords or tokens.

## Handover rules
- **Created for:** a change of support level (agent escalation, automatic escalation from a reply or waiting, admin override with its reason) and agent-to-agent reassignment of a ticket that already had a support reply.
- **Not created for:** routine first assignment, queue rebalancing of untouched tickets, or a reopen (same level and agent).
- **Same transaction as the transfer:** if the summary can't be built, the handover stores references to the raw recent messages (`fallback_raw`) and the transfer still goes through.
- **Immutable:** the code refuses any update; a correction is a new handover with `supersedes_id`.
- **Retention:** kept for the life of the ticket, like messages.

## API (all under `/api`, cookie sign-in)
| Method & path | Who | Returns |
|---|---|---|
| `GET /tickets/{id}/summary` | the customer (customer-facing fields only), agents who can see the ticket, admins | `{status, reason, latest_message_id, summary}` |
| `GET /tickets/{id}/summary/status` | same | `{status, revision, method, updated_at, latest_message_id}` |
| `POST /tickets/{id}/summary/refresh` | agents and admins (rate-limited per ticket) | 202 + summary; returns the current one if nothing changed |
| `GET /tickets/{id}/messages?cursor=&limit=` | anyone who can see the ticket | messages after `cursor` (a message id), oldest first; without parameters: full history |
| `GET /tickets/{id}/messages/since/{message_id}` | same | saved messages after that one (missed while disconnected) |
| `POST /tickets/{id}/resume` | same | `{ticket, messages (recent), has_earlier, cursor, summary status}`; never creates anything |
| `POST /tickets/{id}/messages` | same | accepts `client_message_id`: 201 new, 200 when it's a retry |
| `GET /tickets/{id}/handovers` | agents who can see the ticket, admins (customers: 403) | newest first, with snapshots |
| `GET /tickets/{id}/handovers/{handover_id}` | same | one snapshot |

Errors use the app's usual `{"detail": "..."}`. A ticket you may not see answers 404, exactly like one that doesn't exist.

## Settings (`backend/.env`)
| Setting | Default | Meaning |
|---|---|---|
| `TICKET_SUMMARY_ENABLED` | `true` | rule-based summaries; off = summaries go stale, handovers use raw messages |
| `TICKET_SUMMARY_LLM_ENABLED` | `false` | optional local AI rewrite (measured too slow and inaccurate on CPU) |
| `TICKET_SUMMARY_LLM_MODEL_PATH` | empty | local folder of the model, never from a request |
| `TICKET_SUMMARY_LLM_TIMEOUT_SECONDS` | `10` | per job |
| `TICKET_SUMMARY_MAX_INPUT_MESSAGES` | `50` | how many recent messages a summary reads |
| `TICKET_SUMMARY_RECONCILE_INTERVAL_MINUTES` | `60` | periodic check against the full history |
