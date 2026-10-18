# Technical deep-dive

How every part of the Support Triage Router works, explained simply but completely, so anyone on the team can answer any judge question.
Plain-language overview: [TEAM-GUIDE.md](TEAM-GUIDE.md) · Running and testing: [HOW-TO-RUN-AND-TEST.md](HOW-TO-RUN-AND-TEST.md) · Going online: [DEPLOYMENT.md](DEPLOYMENT.md)

**Contents**
1. [The big picture](#1-the-big-picture)
2. [Technology, and why each piece](#2-technology-and-why-each-piece)
3. [Architecture](#3-architecture)
4. [Life of a ticket](#4-life-of-a-ticket)
5. [Reading the text: sentiment, urgency, emergencies](#5-reading-the-text-sentiment-urgency-emergencies)
6. [Customer value](#6-customer-value)
7. [The priority score](#7-the-priority-score)
8. [Routing: who gets the ticket](#8-routing-who-gets-the-ticket)
9. [Tuning: how the numbers were chosen](#9-tuning-how-the-numbers-were-chosen)
10. [A worked example](#10-a-worked-example)
11. [Making a ticket go red](#11-making-a-ticket-go-red)
12. [Help articles and automatic answers](#12-help-articles-and-automatic-answers)
13. [Suggested reply](#13-suggested-reply)
14. [Ticket summaries](#14-ticket-summaries)
15. [Handovers](#15-handovers)
16. [Never losing a conversation: recovery](#16-never-losing-a-conversation-recovery)
17. [Integrity review aid](#17-integrity-review-aid)
18. [Other features](#18-other-features)
19. [Live updates](#19-live-updates)
20. [Accounts and security](#20-accounts-and-security)
21. [The database](#21-the-database)
22. [Data sets and how we measured](#22-data-sets-and-how-we-measured)
23. [Tests](#23-tests)
24. [Deployment](#24-deployment)
25. [What changed in the model, and why](#25-what-changed-in-the-model-and-why)
26. [Honest limits](#26-honest-limits)
27. [Judge questions](#27-judge-questions)

---

## 1. The big picture

Support teams usually answer tickets in arrival order, so a furious enterprise customer whose system is down waits behind someone asking where their invoice is.

Our app **reads every ticket the moment it arrives**, works out:
- how **frustrated** the customer is
- how **urgent** the problem is
- how **valuable** the account is

It turns that into **one priority score from 0 to 100 that comes with its reasons**, and sends the ticket to the right place:

| Where | What goes there |
|---|---|
| **Answered automatically** | a simple, calm question with a confident help-article match |
| **Level 1 · General Support** | accounts, billing, plans, how-to |
| **Level 2 · Technical Support** | bugs, outages, integrations, data, slowness |
| **Level 3 · Expert Escalation** | emergencies, very upset or high-value customers, very high scores; live chat and callbacks |

Around that core:
- **Live escalation:** a ticket moves up a level within a second when the customer gets angrier, the ticket waits too long, or an agent escalates.
- **Summaries and handovers:** nobody starts from zero after a transfer.
- **Recovery:** a lost connection or expired sign-in never loses a message.
- **Integrity review aid** for admins (optional).

**Everything runs on free, local software: no paid APIs, and no customer data leaves the server.**

---

## 2. Technology, and why each piece

| Layer | Technology | Why we chose it |
|---|---|---|
| Backend language | Python 3 | The AI libraries are Python |
| Web framework | **FastAPI** on **Uvicorn** | Fast; checks every request against a schema automatically; API docs at `/docs` |
| Request checking | **Pydantic v2** | Every input has rules (lengths, allowed values); bad input is refused with a clear error |
| Database | **PostgreSQL**, through **SQLAlchemy 2** | A real, production database; the same one on the laptop and online (Neon) |
| AI models | **Hugging Face Transformers** + **PyTorch** (CPU) | Free, run on our own machine, no API keys |
| Meaning matching | **sentence-transformers** (MiniLM) | Compares texts by meaning, not exact words |
| Classic machine learning | **scikit-learn** | The trained frustration model; a word-based fallback (TF-IDF) |
| Documents | **pypdf** (PDF), Python's own zip/XML tools (DOCX) | Read customer attachments for the integrity aid |
| Website | **React 18**, React Router, **Vite** | Separate pages per role, fast builds |
| Look | **Tailwind CSS** with colour variables | The Nordic design, light and dark mode |
| Live updates | **Server-Sent Events (SSE)** | The server pushes changes to open browsers |
| Sign-in | scrypt passwords, signed cookies, **Google sign-in** | Safe defaults, all free |
| Tests | **pytest** | 188 automated tests |

---

## 3. Architecture

```
Browser (React app)
   │  normal requests  /api/...        live updates  /api/events (SSE)
   ▼
Website host (Vite locally, Vercel online): forwards /api to the backend, so it's one website address
   ▼
FastAPI backend (one process)
   ├─ Sign-in check → role check on every request
   ├─ Triage pipeline:  read text → customer value → priority → routing → pick an agent
   ├─ AI: rules engine + RoBERTa (tone) + emotion model + MiniLM (meaning) + trained frustration model
   ├─ Summaries & handovers (written in the same database transaction as each change)
   ├─ Background helpers: re-score waiting tickets every 30 s; check summaries hourly;
   │                      integrity checks (optional)
   ├─ Event bus → live updates, filtered so each person only receives what they may see
   └─ PostgreSQL (everything: tickets, messages, files, summaries, handovers, settings)
```

Key design choices, in plain words:
- **One website address.** The browser only ever calls `/api` on the site it loaded. The website host forwards those calls to the backend. This lets the sign-in cookie be locked down (`HttpOnly`, `SameSite=Lax`) with no cross-site problems.
- **One backend process, clean layers.** `api/` (endpoints) → `services/` (business logic) → `nlp/` (AI) → `models.py` (tables).
- **The AI can never stall the app.** Models load in the background at start-up. Until they're ready, or if a call takes longer than 3 seconds, the rules engine answers instead.

---

## 4. Life of a ticket

When a customer submits a ticket (`POST /api/tickets` → `process_ticket()`):

1. **Check the input:** category exists, 1–5,000 characters, the person is signed in.
2. **Read the text:** frustration, urgency, problem type, emergencies, language (section 5).
3. **Customer value** from the customer record (section 6).
4. **Extra points:** a 3rd contact within a week; renewing soon while unhappy.
5. **Priority score** (section 7).
6. **Help-article match** (section 12).
7. **Routing decision:** answered automatically, Level 1, 2 or 3 (section 8).
8. **Pick an agent:** the least busy agent at that level who is *Available* and under their limit; otherwise it waits in the level's queue.
9. **Save** the ticket and an *explanation* (every number and reason behind the score), plus its first **summary**.
10. **Tell the right browsers** (live update) and, if switched on, queue an **integrity check**.

After that:

| Event | What happens |
|---|---|
| The customer replies | The reply is read; frustration can only go **up**; new emergencies are added; the ticket is re-scored and can move **up** a level. A resolved ticket reopens. |
| "No, I need a person" on an automatic answer | Frustration +0.2, sent to Level 1, and higher if the score says so. |
| Every 30 seconds | Waiting tickets are re-scored (waiting raises priority); free agents pick up waiting tickets. |
| An agent escalates / an admin overrides | The ticket moves, a **handover** snapshot is frozen, and the decision is saved for retraining. |

---

## 5. Reading the text: sentiment, urgency, emergencies

Every ticket and every customer reply goes through `analyse(text)`, which returns:

| Result | Range | Meaning |
|---|---|---|
| frustration | 0–1 | how upset the customer is |
| urgency | 0–1 | how time-critical the problem is |
| problem type ("intent") | label | billing dispute, bug, how-to… |
| emergencies ("critical flags") | list | security, safety, legal, outage |
| language | en / hi-en / hi | English, Hinglish, Hindi script |
| how sure | 0–1 | confidence in the reading |

Two layers work together: a **rules engine** (always on) and **AI models** (when loaded).

### 5.1 The rules engine (`app/nlp/rules.py`)

**Emergencies** (word patterns):

| Emergency | Example words |
|---|---|
| legal | lawyer, lawsuit, sue, court, regulator, consumer forum (also notifies a manager) |
| safety | fire, smoke, sparked, burning smell, melted, electric shock, overheating |
| security | hacked, unauthorised, fraud, stolen, phishing, "someone logged into my account" |
| outage | outage, "site / server / checkout … is down / offline", Hinglish "site band ho gaya" |

Two protections against false alarms:
- **Negation:** if *not, no, never, didn't, nahi…* appears in the 4 words before, it's ignored. "We were **not** hacked" raises nothing.
- **Look-alikes** are blanked out first: "smoke test", "SLA breach", "fired up", "tennis court".

**Problem type:** 10 patterns, first match wins. Each has a base urgency (tuned on data, section 9) and a "routine" mark (routine questions may be answered automatically):

| Problem type | Base urgency | Routine |
|---|---|---|
| billing dispute | 0.60 | no |
| locked out / access | 0.60 | no |
| complaint | 0.55 | no |
| bug | 0.55 | no |
| cancellation | 0.50 | no |
| performance | 0.40 | no |
| invoice | 0.10 | yes |
| how-to | 0.10 | yes |
| password reset | 0.05 | yes |
| feature request | 0.05 | yes |
| nothing matched ("other") | 0.55 | no |
| security / safety / outage / legal | 1.0 / 1.0 / 0.95 / 0.9 | no (fixed by design) |

**Urgency boosts** on top (capped at 1.0):
- "ASAP", "urgent", "immediately", "deadline", "production", "all our users": +0.15 each
- "today", "by EOD": +0.10
- "losing money": +0.20
- "blocked", "stuck": +0.10
- Hinglish "jaldi, turant, abhi": +0.15; "kal tak": +0.10

**Four frustration signals** (each 0–1):

| Signal | How it's measured |
|---|---|
| negative tone | weighted word list ("terrible" 0.5, "fed up" 0.6), including Hindi words (*bakwas, ghatiya*) |
| anger & sarcasm | weighted list: "furious" 0.8, "how many times" 0.6, sarcasm such as "thanks for nothing" 0.8, "great, just great" 0.7 |
| exclamation marks | number of "!" (up to 5) ÷ 5, plus 0.2 for "??". **Capital letters are not counted** (see 5.4) |
| threat to leave | "cancel", "competitor", "chargeback", "bad review"…; 2 hits = full |

**Language:** Devanagari letters → Hindi; 2 or more Hinglish words (hai, mera, nahi, chahiye…) → Hinglish.

### 5.2 The AI models (`app/nlp/hf.py`)

| Model | What we take from it |
|---|---|
| RoBERTa sentiment (`cardiffnlp/twitter-roberta-base-sentiment-latest`) | probability the text is negative |
| Emotion model (`j-hartmann/emotion-english-distilroberta-base`) | anger = anger + disgust + half of sadness |
| MiniLM (`all-MiniLM-L6-v2`) | a "meaning fingerprint" of 384 numbers for any text |

**This is the sentiment analysis:**
- **RoBERTa** reads the whole sentence in context, so it catches negativity no word list has ("I've waited since Monday and still nothing").
- **The rules** add what models are bad at: sarcasm ("great, just great" sounds positive to a model), Hinglish, exclamation marks and threats to leave.

**Problem type from meaning:**
1. Each of 12 problem types has 2–4 example sentences.
2. The ticket's meaning fingerprint is compared with each example, and each type keeps its closest match.
3. A softmax turns those scores into probabilities.
4. The model's urgency estimate blends the problem types' urgencies by those probabilities.
5. Final urgency = half the rules' estimate + half the model's, plus the boosts.
6. Emergencies always win.

### 5.3 The frustration model (trained, not guessed)

A **logistic regression** trained on 252 labelled training tickets turns the six signals into one number:

```
frustration = sigmoid( −2.89 + 0.56·tone(model) + 0.16·anger(model) + 0.50·tone(rules)
                       + 5.62·anger&sarcasm(rules) + 1.59·exclamation marks + 3.41·threat to leave )
```
- **What the data taught us:** anger/sarcasm cues and threats to leave matter most. The emotion model's anger counts for little, because it over-reads anger in calm problem reports.
- **"Highly frustrated" means ≥ 0.41**, chosen by cross-validation to catch as many angry customers as possible (missing one costs more than a false alarm).

### 5.4 Why capital letters don't count as anger

The first version counted ALL-CAPS words as "shouting", as is common in sentiment tools. We **tested** whether it helps (`python -m eval.shouting_ablation`): the model was trained three ways on the training tickets and compared on the held-out test tickets.

| Version | AI mode (used by the app) | Rules-only fallback | Calm messages typed in capitals |
|---|---|---|---|
| CAPS + exclamation marks (old) | recall 0.83, precision 0.94 | recall 0.83 | scored 0.11–0.18 |
| **Exclamation marks only (now)** | **recall 0.83, precision 0.94: identical** | recall 0.79 | **scored 0.05–0.08** |
| No punctuation signal at all | recall 0.79 | recall 0.79 | 0.06–0.09 |

Capitals added nothing in AI mode, and they push up the scores of calm people who simply type in capitals (older users, caps lock, accessibility tools). So capitals were dropped and exclamation marks kept. The cost is a small drop in the rules-only fallback, which is only used when the AI models are unavailable.

---

## 6. Customer value

`app/services/value.py`, a number from 0 to 1:
```
value = 0.40 × plan + 0.30 × spend (total ÷ 50,000, max 1) + 0.20 × risk of leaving + 0.10 × renewing soon
plan: Enterprise 1.0 · Pro 0.6 · Basic 0.3 · Free 0.1
risk of leaving = the larger of the record's figure or (tickets in 30 days ÷ 5)
renewing soon: within 30 days 1.0 · within 90 days 0.5 · otherwise 0
```
**Honest note:** there's no data to tune this formula against (we'd need real revenue and churn outcomes), so it's a **business setting**, not a learned model. That's also why customer value can't escalate a ticket on its own unless the score is also high (section 8).

---

## 7. The priority score

`app/services/priority.py`:
```
priority = 100 × (0.25 × frustration + 0.25 × urgency + 0.30 × customer value + 0.20 × waiting)
           + extra points
waiting = minutes waited ÷ the plan's reply-by time (max 1)
```

**Reply-by time** (SLA = service level agreement) is the response promise per plan: Enterprise 60 min, Pro 120, Basic 240, Free 480.

| Extra points | How many | When |
|---|---|---|
| Contacted 3+ times this week | +15 | 3rd ticket or more within 7 days |
| Renewing soon and unhappy | +10 | renewal within 14 days and negative tone |
| Close to its reply-by time | 0 → +50 | starts at 75% of the reply-by time, full +50 at 125% |

- The last row is the **anti-starvation rule**: a ticket that waits long enough rises to the top, so nobody is forgotten.
- It only affects **queue order**, not escalation. A ticket isn't sent to an expert just for waiting.
- **Priority never goes down** while a ticket waits, and an admin's manual priority is never changed.
- The **two biggest contributions** become the reasons shown in the app, e.g. "High-value customer (91%)", "Time-critical issue (100%)".

---

## 8. Routing: who gets the ticket

`decide()` in `app/services/router.py`, checked in this order:

| # | Rule | Goes to |
|---|---|---|
| 1 | any emergency (legal also notifies a manager) | **Level 3** |
| 2 | help-article match ≥ 0.69 **and** routine **and** calm (frustration < 0.4) **and** score < 40 **and** sure enough | **answered automatically** |
| 3 | frustration ≥ 0.41 | **Level 3** |
| 4 | customer value ≥ 0.70 **and** score ≥ 50 | **Level 3** |
| 5 | score ≥ 65 | **Level 3** |
| 6 | technical problem (bug, outage, integration, performance) or a technical category | **Level 2** |
| 7 | everything else | **Level 1** |

Rules that always hold:
- tickets only move **up** automatically, never down
- the category the customer picked is just a starting point
- an admin can **lock** a ticket's level

---

## 9. Tuning: how the numbers were chosen

We didn't copy numbers from the idea document. Here's what was **learned or tuned on data**, and what is a business setting:

| Number | How it was set |
|---|---|
| Frustration model weights + the 0.41 cut-off | trained on 252 training tickets |
| What counts as "shouting" | tested: capital letters removed, exclamation marks kept (section 5.4) |
| Help-article cut-offs (0.46 suggest / 0.69 automatic) | tuned on separate validation questions |
| **Urgency of each problem type** | coordinate search for the best urgency accuracy on the training tickets (`eval/tune_weights.py`) |
| **Priority weights 25 / 25 / 30 / 20** | grid search (steps of 0.05) in the busy-day simulation on **five simulated days built only from training tickets**. Goal: fewest late replies plus shortest waits for urgent, highly frustrated and high-value customers. Old hand-set values: 30 / 30 / 25 / 15 |
| Level 3 cut-off 65 | re-checked on training data with the new weights: still best |
| Anti-starvation ramp | tuned on separate simulated days |
| Customer value formula, +15 / +10 extra points, high-value rule | **business settings**: there's no outcome data to tune them against |

**Result on the held-out test data** (never used for tuning):

| | Before tuning | After |
|---|---|---|
| Urgency accuracy (F1), AI mode | 0.84 | **0.86** |
| Urgency accuracy (F1), rules only | 0.78 | **0.96** |
| Late replies on the busy test day | 5 | **0** |
| High-value customers' average wait | 16.9 min | **8.8 min** |
| Urgent tickets' average wait | 35.5 min | 42.3 min (a bit worse, still 32% better than arrival order) |
| Emergency, frustration and escalation results | unchanged | unchanged |

**Honest caveats:**
- The rules-only urgency (0.96) now beats the AI mode (0.86) on our test set. That's because the tuned rules fit our template-generated tickets very well; on real tickets, the AI's understanding of meaning should generalise better.
- The test day's slowest 5% of urgent tickets wait longer than with arrival order: that's the price of reaching zero late replies.

---

## 10. A worked example

Northwind Logistics (Enterprise, spent 92,000, risk of leaving 0.55, renewing in 30 days, reply-by 60 min) writes:
> "Our production dashboard has been DOWN for an hour. We will cancel if this is not fixed ASAP!"

Computed by the real code:

| Step | Result |
|---|---|
| Emergency | **outage** ("dashboard … DOWN") |
| Urgency | **1.0** (outage 0.95 + "production" + "ASAP", capped) |
| Frustration | **0.43** (negative tone 0.94 from RoBERTa, anger 0.42, one "!", "cancel"; the capitals in "DOWN" don't count) |
| Customer value | 0.40×1.0 + 0.30×1.0 + 0.20×0.55 + 0.10×1.0 = **0.91** |
| Waiting | 12 of 60 minutes = 0.2 |
| Priority | 25.0 (urgency) + 10.8 (frustration) + 27.3 (value) + 4.0 (waiting) = **67** |
| Routing | rule 1, emergency → **Level 3 · Expert Escalation** |
| Reasons shown | "High-value customer (91%)", "Time-critical issue (100%)" |

---

## 11. Making a ticket go red

**Red = Level 3 · Expert Escalation**: red badge, red queue marker, red emergency chips, "manager notified" for legal. Try these as a customer (checked with the AI models on):

| Type in | Category | Result | Why |
|---|---|---|---|
| Someone changed my password and I can't get into my account. I think I was hacked. | Account & login | 🔴 Level 3 | emergency: security |
| The website is down for everyone in our office, nothing loads. | Outage | 🔴 Level 3 | emergency: outage |
| Our lawyer will take legal action if the refund is not processed this week. | Billing | 🔴 + manager notified | emergency: legal |
| My laptop charger from your store sparked and there is a burning smell. | Bug | 🔴 Level 3 | emergency: safety |
| The app has crashed 3 times today and I lost my work AGAIN!!! This is ridiculous, fix it NOW or I cancel. | Bug | 🔴 Level 3 | frustration 0.97 |
| Great, just great. Third time this week the sync broke. Thanks for nothing. | Feedback | 🔴 Level 3 | sarcasm: frustration 0.96 |
| Paisa kat gaya do baar, bahut bakwas service hai. Turant refund karo warna cancel kar dunga!! | Billing | 🔴 Level 3 | Hinglish anger + threat |

Should **not** go red: "How do I change my profile picture?" (Level 1), "The export button does not work" (Level 2), "We were not hacked, I just want to enable two-factor login" (Level 1, negation).

**Live:** on a calm ticket, reply "This is RIDICULOUS!!! Nobody has helped me. Fix it NOW or we cancel!". It turns red within a second.

---

## 12. Help articles and automatic answers

- Each article is stored as its title **plus each example question separately**; an article's score is its *closest* match, so a reworded question still matches.
- Matching uses MiniLM meaning fingerprints (or word-based TF-IDF as a fallback).
- **Cut-offs tuned on validation questions:** *suggest* from 0.46, *answer automatically* from 0.69.
- Only **public** articles are ever shown to customers; internal guides never are.
- **"These articles might help"** appears while a customer types a new ticket.
- Automatic answers ask **"Did this help?"**. "No" sends the ticket to a person.

---

## 13. Suggested reply

`app/services/replies.py`. **A template, not a generative AI:** instant and predictable, and it can't make things up. The agent always edits before sending.

| Part | How it's chosen |
|---|---|
| Greeting | "Hi {first name}," |
| Empathy | very upset → "I'm really sorry about this…"; somewhat → "Sorry for the trouble…"; calm → "Thanks for getting in touch." |
| Body | emergency → that emergency's fixed next step (security: "don't share your password… I'm securing your account now"); a good help article → its answer; otherwise the next step for the problem type ("Could you attach a screenshot…") |
| Promise | Level 3: "within 30 minutes"; otherwise from the reply-by time |

---

## 14. Ticket summaries

**What:** a **View summary** button on every ticket card and ticket page opens a short digest of the ticket. Code: `app/services/summarization.py`.

**How it's built (rule-based, milliseconds, no AI guessing):**
- It reads only **saved** messages (the last 50) and the ticket's own fields.
- Every quoted line keeps **the id of the message it came from**, e.g. "message #52".
- If a pattern isn't there, the field stays empty. **Nothing is invented.**

| Field | Where it comes from |
|---|---|
| Problem | the subject and first sentences of the description |
| What the customer wants | a customer sentence like "I need…", "please…", "how do I…" |
| Customer says | customer sentences stating something happened, **labelled as claims, not facts** |
| Confirmed | only records (plan on file, category, level) or an agent sentence that explicitly confirms ("I can confirm…") |
| Already tried / worked / didn't work | sentences with "tried, restarted, cleared…", or explicit outcomes ("that worked", "still not working") |
| Promised by support | agent sentences with "I'll / we will" |
| Still to do | those promises (owner: support) + agent requests ("could you send…", owner: customer) |
| Open questions | customer questions with no support reply after them |
| Status, emergency flags | copied from the ticket, never re-worked out |
| Suggested next step | a simple rule, **labelled as a rule** |

**Who sees what:** customers get a simpler version (problem, goal, progress, what was tried, promises, open questions), never claims, internal facts, flags or recommendations.

**Staying fresh:**
- Whenever a message is saved or the ticket's status, level, agent or emergencies change, a new summary version is written **in the same database transaction**.
- It's written in a protected sub-step: if the summary fails, the change itself still goes through.
- Versions are numbered and kept, and an older one can never overwrite a newer one.
- An hourly check catches anything missed.

**States shown:** Up to date · Out of date (with the time of the last good one) · Updating · Last update failed (the last good one is still shown) · Not available (with the reason).

**The AI option, measured and switched off:**
- We tested a free local model (Qwen2.5-0.5B, Apache-2.0) on the laptop: **16.5 s per summary**, and **3 factual errors** in one summary (for example, it said the *customer* agreed to reverse a payment when the *agent* had promised it).
- So the rule-based version is used. The AI option stays in the code, off. Even switched on, it could only reword three plain-text fields and never the quoted lists.

---

## 15. Handovers

**What:** when a ticket moves to another **level** or another **agent**, a **frozen snapshot** is saved, and the receiving agent sees it in a **Handover** box above the reply field. Code: `app/services/handover.py`.

**Contents:**
- from → to (agent and level), why, who did it, when
- what was tried, what's confirmed, what the customer says
- what's still to do, what was promised, open questions, the suggested next step
- **priority and emergencies at the moment of transfer** (labelled as such)
- the ids of the recent messages

**When:**
- **Created:** any level change (agent escalation, automatic escalation, admin override with its required reason), and reassigning a ticket that already had a support reply to another agent (an agent goes busy or offline, or another agent claims it).
- **Not created:** the very first assignment, queue shuffling of untouched tickets, a reopen (same level and agent).

**Safety:**
- Built **in the same transaction** as the transfer.
- If the summary can't be built, it falls back to **references to the raw recent messages** and says so ("Built from raw messages"). **The transfer always succeeds.**
- **Can never be edited:** the code refuses any change. A correction is a new snapshot pointing at the old one.
- Never changes priority, reply-by time, emergencies, locks or level (tested).
- Customers can never see handovers.

---

## 16. Never losing a conversation: recovery

| Situation | What happens |
|---|---|
| **Sending a message** | The browser gives each message a random id. The database allows one message per *(ticket, author, id)*, so a retry, even two at the same moment, returns the **original** message instead of a copy. |
| **Message states** | *Sending…*, then saved; or *Not sent – Retry*. Never shown as saved before the server confirms. |
| **Unsent text** | Kept in the browser per ticket; survives a refresh; cleared only after the server confirms. No passwords or tokens are ever stored there. |
| **Connection drops** | Sidebar shows *Reconnecting… / Offline*; the chat offers **Resume conversation**. The browser retries with growing waits (1 s, 2 s, 4 s… up to 30 s). |
| **Reconnected** | *Catching up…*: every page re-fetches from the server (live updates sent while you were away aren't replayed), then *Live*. |
| **Page refresh** | The ticket loads from its web address. Nothing ever creates a ticket on load. |
| **Sign-in expired** | The sign-in page says "Your session expired" and returns you to the same ticket afterwards. |

---

## 17. Integrity review aid

Admins only, **off by default**. Details: [integrity/DECISIONS.md](integrity/DECISIONS.md).

After a ticket, customer reply or customer PDF/DOCX upload is saved, a background worker checks four things:
1. **AI-like writing:** a local English-only detector model (ModernBERT, Apache-2.0, labels checked before use); its score is **not a probability**.
2. **Near-identical tickets** from the same or another customer (shared outages don't count).
3. **Claims that clash with our own records:** e.g. "first time contacting you" when earlier tickets exist. Payment claims can't be checked: we hold no payment records.
4. **Clear warning signs:** repeated requests to skip checks, or text giving instructions to automated systems.

How it treats the results:
- Clear signs suggest a **manual review**. **AI-like writing alone never does.**
- A versioned rule set decides; there's no "fraud score".
- It never changes the ticket or what the customer sees.
- Confirming a concern requires a written reason, which is logged with the reviewer's name.
- **Agents** see only two yes/no hints on queue cards and the ticket page: a grey **"AI-like writing"** chip (tooltip: not evidence on its own) and **"review suggested"**. No score, no evidence, no actions. Customers see nothing.

---

## 18. Other features

| Feature | How it works |
|---|---|
| Search (Ctrl K) | text search plus article matching, limited by role: customers see public articles and their own tickets; agents add internal guides and their level's tickets; admins see all |
| Guides for this ticket | internal guides matched to the problem type and emergencies (e.g. the security runbook) |
| Incidents | groups near-identical open tickets (MiniLM similarity ≥ 0.70); "reply to all" and "resolve all" |
| Suggested new help topics | the same grouping on questions nothing answered |
| Availability | Available / Busy / Offline; only available agents under their limit get tickets |
| Analytics | computed live from the database: tickets per hour/day, solved by help articles, escalations, response and resolution times |
| Try other settings | re-ranks the queue with other weights without saving anything |
| Retraining | with 30 or more agent escalations and admin overrides, proposes the Level 3 and frustration cut-offs that agree with agents most; the admin must click Apply |
| Callbacks | at Level 3 the customer can request a call |
| Admin menu | grouped into *Daily work* (Overview, Incidents, Users & workload, Knowledge base), *Reports* (Analytics, Insights), *Tools & settings* (Integrity, Tuning); demo tools and technical details sit in collapsible sections |

---

## 19. Live updates

- **Server-Sent Events:** each open browser keeps one connection; the server pushes small JSON events (ticket created, escalated, message, typing, summary updated, handover created, integrity results…).
- **Filtered per person:** admins get everything; customers only their own tickets; agents their level, tickets that just left it, and tickets assigned to them. Handover and integrity events never reach customers.
- **Events carry ids and states, never conversation text.** The page always re-fetches the real data.
- **Why not WebSockets?** We only need server → browser; SSE is simpler and works through proxies.
- **Limit:** the event bus lives in one process's memory. That's why pages re-fetch after reconnecting. More servers would need a shared bus such as Redis.

---

## 20. Accounts and security

| Area | How |
|---|---|
| Passwords | **scrypt** (deliberately slow and memory-hungry, with a random salt); at least 8 characters with upper and lower case and a number |
| Sessions | a signed token in an **HttpOnly, SameSite=Lax** cookie; scripts can't read it, other sites can't use it. "Remember me" = 7 days, otherwise until the browser closes |
| Roles | every request checks who you are and what you may see; customers never see internal scores |
| Brute force | failed sign-ins slowed per account; sign-up, recovery and reset requests per network address |
| Google | the server verifies Google's signed token and that the email is verified |
| Forgot password, no email needed | a one-time **recovery code** (stored only as a hash, replaced after use), or a one-time admin **reset link** (only a hash stored, single use, 30 minutes) |
| Files | PNG, JPG, PDF, DOCX checked by their **real content**, not the name; 5 MB, 5 per message; stored in the database; served only after a permission check |
| Input | length limits everywhere; unknown fields refused on the newer endpoints; database queries are parameterised (no SQL injection); React escapes text (no script injection) |
| Secrets | `.env`, demo passwords and model files are never committed |

---

## 21. The database

**PostgreSQL only**, on the laptop and online.
- At start-up the backend creates any missing tables and applies small **additive** upgrades (new columns only, nothing deleted), so an older database keeps all its data. This was tested on a copy of the real database first.
- Tests run in a **throwaway area (schema)** of the database that's removed afterwards.

| Table | Holds |
|---|---|
| customers | the mock customer records: plan, spend, risk of leaving, renewal, reply-by time |
| users | accounts, password hash, role, availability, capacity, recovery-code hash |
| tickets | text, category, scores, problem type, emergencies, level, status, agent, explanation |
| messages | the conversation, including each message's client id (for safe retries) |
| attachments | file details and the file itself |
| kb_articles | help articles and internal guides |
| incidents, callback_requests, feedback | grouped tickets, call requests, agent decisions (for retraining) |
| ticket_summaries | numbered summary versions |
| handovers | frozen transfer snapshots |
| integrity_assessments, integrity_review_actions | integrity checks and the audit trail |
| password_resets, app_settings | reset links (hashed), saved tuning |

All times are stored in UTC.

---

## 22. Data sets and how we measured

| File | Rows | Purpose |
|---|---|---|
| `data/tickets_seed.csv` | 42 | demo tickets loaded into the app |
| `data/tickets_labelled.csv` | 384 (44 Hinglish) | the exam with an answer key: urgency, frustration, emergency, problem type |
| `data/kb_eval.csv` | 71 | questions with the article each should match |
| `data/customers.json` | 20 | mock customer records |

- The 384 labelled tickets are **synthetic**: built from problem templates combined with tones (polite, angry, sarcastic, Hinglish) and labelled with a written guide.
- They're **split by template**: 252 for training, **132 for testing**, so test sentences were never seen while tuning.

**Results on the 132 test tickets (AI mode):**

| Measure | Target | Result |
|---|---|---|
| Urgency accuracy (F1) | ≥ 0.75 | **0.86** |
| Angry customers caught | ≥ 0.80 | **0.83** (alarms right 94% of the time) |
| Expert escalations that were right | ≥ 0.80 | **0.97** |
| Emergencies caught | — | **100%** |
| Automatic answers that were correct | ≥ 0.90 | **0.96** |
| Time per ticket | < 2 s | **≈ 0.2 s** |

**A simulated busy day** (120 tickets, 3 agents, 8 hours, demand 29% over capacity), versus arrival order:
- urgent tickets wait **32% less**
- high-value customers wait **84% less**
- late replies **11 → 0**

Trade-off: routine tickets wait about 22% longer, but still within their reply-by time.

Re-run everything: `python -m eval.run_all` (about 3 minutes). Re-tune: `python -m eval.tune_weights`.

---

## 23. Tests

**188 automated tests**, all passing, in `backend/tests/`:
- **reading the text:** negation, sarcasm, Hinglish, safety words, capitals not counted as anger
- **scoring and routing:** priority maths, anti-starvation, routing rules, waiting
- **AI fallback:** models missing or slow
- **accounts:** passwords, cookies, throttling, recovery codes, reset links; every role's permissions
- **escalation, attachments** (real file type, size, access), search, incidents, analytics, retraining
- **integrity:** detector, documents (encrypted, scanned, zip bombs), duplicates, records, rules, admin-only access, "never changes the ticket"
- **summaries, handovers, recovery:** nothing invented, versions, AI output validation, handover per transfer, raw fallback, immutability, safe retries, session expiry

---

## 24. Deployment

**All free.** Full steps: [DEPLOYMENT.md](DEPLOYMENT.md).

| Part | Host |
|---|---|
| Backend + AI models | **Hugging Face Spaces** (Docker; 16 GB memory, enough for the full AI) |
| Database | **Neon** (PostgreSQL) |
| Website | **Vercel**, forwarding `/api` to the backend so it stays one website address |

The backend image includes the AI models, so it never downloads anything at run time. A GitHub Action pushes the backend to the Space on every change.

---

## 25. What changed in the model, and why

Every change below was tested on data the model never trained on, or checked in the running app.

| Change | Before | After | Evidence |
|---|---|---|---|
| Priority weights (frustration / urgency / value / waiting) | 30 / 30 / 25 / 15, copied | **25 / 25 / 30 / 20**, tuned | simulation on training days; test day: late replies 5 → 0, high-value waits 16.9 → 8.8 min, urgent waits 35.5 → 42.3 min |
| Urgency of each problem type | hand-set | tuned on training labels: billing dispute 0.55→0.60, locked out 0.55→0.60, cancellation 0.45→0.50, bug 0.45→0.55, complaint 0.35→0.55, password reset 0.15→0.05, other 0.30→0.55 (invoice, how-to, feature request, performance unchanged) | urgency F1 on test: AI 0.84 → 0.86, rules 0.78 → 0.96 |
| "Shouting" | CAPS + exclamation marks | **exclamation marks only** | AI-mode results identical; calm capitals no longer raise frustration (section 5.4) |
| Frustration model | trained with CAPS | **retrained**; cut-off 0.42 → **0.41** | test recall 0.83, precision 0.94 (unchanged) |
| Safety emergency words | missed "sparked", "burning smell", "melted" | **caught** | found while testing examples; test added |
| Level 3 score cut-off | 65 | 65 (re-checked with new weights: still best) | escalation F1 on training data |
| AI-writing detector (integrity) | — | **ModernBERT detector added**, off by default, admin review aid | licence and labels verified; very unstable on short or edited text (tested) |
| Ticket summaries | — | **rule-based, quoted with sources** | a local AI model was measured: 16.5 s per summary and 3 factual errors, so it's off |
| Reason texts shown to people | "Critical rule", "Ageing upgrade", "SLA at risk"… | "Emergency", "Waited too long", "Close to its reply-by time"… | wording only; same logic |

**Not changed, on purpose:**
- **The customer-value formula and the +15 / +10 extra points:** no outcome data exists to tune them, so they're documented as business settings.
- **The help-article cut-offs (0.46 / 0.69):** already tuned on validation data.

## 26. Honest limits

- **Synthetic test data:** real tickets would need re-tuning.
- **Mock customer records:** the customer-value formula and the extra points are business settings, not learned.
- **Single process:** live updates are in memory; background jobs (integrity, AI refinement) aren't guaranteed to survive a restart, but everything they produce can be rebuilt.
- **Calls** are callback requests, not in-browser voice.
- **Not included:** email, two-factor sign-in, encryption of stored data at rest.
- **AI limits:** the summary AI is off (too slow and inaccurate on CPU); the integrity detector is English-only and not validated on real tickets.

---

## 27. Judge questions

| Question | Answer |
|---|---|
| Why not ChatGPT? | Free, local, ≈0.2 s, and predictable: we can guarantee "security issue = always an expert". No customer data leaves the server. |
| Did you just copy weights? | No. Urgency per problem type and the priority weights were tuned on training data and checked on held-out data; the frustration model and help-article cut-offs were trained too. What couldn't be tuned (value formula, extra points) is clearly called a business setting. |
| Does writing in CAPITALS make you look angry? | No. We tested it: capitals added no accuracy, and they unfairly raised the score of calm people who type in capitals, so only exclamation marks count. |
| How does sentiment analysis work? | RoBERTa reads negative tone in context, an emotion model reads anger, rules catch sarcasm, Hinglish, shouting and threats to leave; a model trained on labelled tickets combines them. |
| Are summaries AI-generated? Can they lie? | They're built by rules from saved messages; every line names its source message, claims are labelled as claims, and nothing is invented. We tested a local AI model: it was slow and made errors, so it's off. |
| What happens when a ticket is transferred? | A frozen handover snapshot is saved in the same transaction; the next agent sees it above the reply box. It can't be edited, and the transfer works even if the summary fails. |
| What if the connection drops? | Nothing is lost: messages are only "saved" once the server confirms, retries can't duplicate, drafts survive a refresh, and an expired sign-in returns you to the same ticket. |
| What if the AI is wrong? | Every score is explained; agents escalate, admins override, and those decisions feed retraining. Emergencies use fixed rules. |
| Is prioritising rich customers fair? | Value is 30% of the score; emergencies, angry customers and long waits beat it on any plan, and nobody waits past their reply-by time on the test day. |
| Does the integrity tool accuse people of using AI? | No. AI-like writing alone never even suggests a review; a person must check, and confirming needs a written reason. |
| Why PostgreSQL? | A real production database, identical on the laptop and online; tests run on it too. |
| Does it scale? | Scoring is quick and stateless. Next steps: several backend processes with a shared event bus (Redis) and the models on their own service. |
| Is it secure? | Hashed passwords, locked-down cookies, role checks everywhere, throttled sign-in, real file-type checks, private files, no SQL injection. |
