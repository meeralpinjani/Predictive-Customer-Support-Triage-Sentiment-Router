# Predictive Customer Support Triage & Sentiment Router

**Team AlgoAmigos · HelloWorld KIT '26**

Support queues answer tickets first come, first served, so a furious enterprise customer whose production is down waits behind someone asking how to download an invoice. This system reads every ticket, measures **frustration**, **urgency** and **customer value**, merges them into **one explainable 0-100 priority score**, and routes the ticket: an instant knowledge-base answer, **Level 1 · General Support**, **Level 2 · Technical Support**, or **Level 3 · Expert Escalation** with live chat and callbacks. Tickets escalate in real time, and waiting time raises priority, so nobody is left behind.

> **New to the project?** Read [docs/TEAM-GUIDE.md](docs/TEAM-GUIDE.md) (plain-language overview) and [docs/HOW-TO-RUN-AND-TEST.md](docs/HOW-TO-RUN-AND-TEST.md) (step-by-step checklist). For judge questions, [docs/TECHNICAL-DEEP-DIVE.md](docs/TECHNICAL-DEEP-DIVE.md) explains every part in detail. To put it online for free, follow [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) (Hugging Face Spaces + Neon PostgreSQL + Vercel). The optional admin **Integrity** review aid is documented in [docs/integrity/](docs/integrity/DECISIONS.md). Ticket summaries, handovers and recovery: [docs/summaries/](docs/summaries/README.md).

## Roles and views

| Role | Gets the role by | Sees |
|---|---|---|
| **Customer** | Signing up (email + password, or Google) and choosing a plan | My tickets · New ticket (category, screenshots, "articles that might help" while typing) · ticket page (conversation with attachments, instant answers, "Did this help?", callback at Level 3) · Help centre (FAQ) |
| **Level 1 · General Support** | An admin assigns it | My queue · ticket workspace (chat with attachments, **Suggest reply**, guides for this ticket, claim / escalate / resolve) · Incidents · Knowledge base · availability switch |
| **Level 2 · Technical Support** | An admin assigns it | Same for Level 2 |
| **Level 3 · Expert Escalation** | An admin assigns it | Same for Level 3, plus live chat and callback scheduling |
| **Admin** | `ADMIN_EMAIL` in `.env`, or promoted by an admin | Overview of all queues · Analytics over time · Insights (evidence) · Incidents · Users & workload · Knowledge-base editor · Tuning (what-if, retrain) |

**Everyone** gets a search bar (Ctrl K), scoped by role:
- **Customers:** help articles and their own tickets.
- **Agents:** articles, internal guides, their level's tickets and those tickets' customers.
- **Admins:** everything.

**Working the queue:**
- **Knowledge base:** public FAQ articles auto-answer customers and fill the Help centre. **Internal guides** (escalation rules, security runbook, legal threats, angry customers, outages, billing, bugs) appear automatically on matching tickets. Admins edit both and see **suggested new topics** from tickets nothing answered.
- **Suggested reply:** a draft with empathy matched to the customer's frustration, plus the right article or next step. The agent edits it before sending.
- **Incidents:** near-duplicate tickets (e.g. one outage, many reports) are suggested as a group. One reply or "resolve" covers every customer.
- **Availability and capacity:** agents set Available / Busy / Offline, and admins set each agent's maximum open tickets. Nobody busy, offline or full gets new tickets; waiting tickets are handed out as capacity frees up.
- **Attachments:** PNG, JPG or PDF, 5 MB each, up to 5 per message.
  - Checked by their real file type (SVG and disguised files are refused).
  - Stored privately and served only to people allowed to see the ticket.

**Admin only:**
- **Analytics over time:** hourly volume, deflection, escalations, first-response and resolution times, all computed live from the database.
- **Retrain from agents:** finds the routing thresholds that best match agents' escalations and overrides. It refuses until at least 30 such decisions exist.

- **Categories:** customers pick a category. *General* categories (account, billing, plans, how-to, feedback) start at Level 1; *technical* ones (bug, outage, integrations, data, performance) start at Level 2.
- **Escalation rule:** the AI can only move a ticket **up**, never below its category. Level 3 can't be chosen; it's reached only by escalation:
  - critical issues (security, legal, safety, outage);
  - high frustration;
  - high-value accounts;
  - a high score;
  - SLA ageing;
  - "the answer didn't help";
  - an angrier customer reply;
  - an agent clicking **Escalate**.
- **Real time:** every change streams live (server-sent events). The receiving level gets a toast, a chime and a bell notification, and the customer sees their ticket move.

**Security:**
- **Passwords:** hashed with scrypt, and must be 8+ characters with upper, lower and a number.
- **Sessions:** signed HttpOnly cookies. "Remember me" keeps you signed in for 7 days; otherwise the session ends when the browser closes.
- **Logins:** failed attempts are throttled.
- **Forgot password:** works without email.
  - A **recovery code** shown once at sign-up (stored only as a hash) lets users reset alone.
  - Without the code, an admin creates a **one-time reset link** (hashed, expires in 30 minutes).
  - The "request help" step answers the same whether or not the account exists.
- Every API endpoint checks the role: customers only ever see their own tickets and never see internal scores; agents only act on their level.

## Results (held-out test set, `python -m eval.run_all`)

| Metric | Target | AI models (default) | Rules fallback |
|---|---|---|---|
| Urgency F1, 3 classes | ≥ 0.75 | **0.86** | 0.96 |
| Frustration recall / precision | recall ≥ 0.80 | **0.83 / 0.94** | 0.83 / 0.94 |
| Escalation precision (sent to Senior that should be) | ≥ 0.80 | **0.97** | 0.97 |
| Critical-issue recall (security, legal, safety, outage) | n/a | **1.00** | 1.00 |
| KB auto-answer accuracy | ≥ 0.90 | **0.96** | 1.00 |
| Safe auto-answers (routine and not angry) | n/a | **0.95** | 0.94 |
| Latency per ticket | < 2 s | **~150-200 ms** | 4 ms |

**A busy simulated day** (120 tickets, 3 agents, demand ≈ 129% of capacity, per-customer SLAs):

| | FCFS | Router | Change |
|---|---|---|---|
| Urgent tickets, avg wait | 62.5 min | **42.3 min** | −32% |
| High-value customers, avg wait | 55.3 min | **8.8 min** | −84% |
| Late replies (past reply-by time) | 11 | **0** | −100% |
| Low-priority tickets, avg wait | 63.8 min | 78.0 min | +22% (within reply-by time) |
| Tickets needing a human | 100% | **86%** | −14% deflected |

The ablation (Insights tab) shows why every signal is needed: sorting by urgency alone is fastest for urgent tickets but starves high-value accounts and breaks SLAs. The full router gives up some urgent speed to keep breaches lowest. Trade-off stated honestly: urgent tickets from free-tier customers (8 h SLA) can wait longer than under FCFS, but within their SLA.

## How it works

```
 web form / API ──► FastAPI ──► NLP pipeline ──────────────────────────────┐
                               · RoBERTa sentiment + emotion  → frustration │
                               · MiniLM issue embeddings + rules → urgency  │
                               · critical flags (negation-aware), Hinglish  │
                               · MiniLM knowledge-base retrieval            │
                                                                            ▼
           customers (mock CRM) ──► value model ──► priority engine ──► router ──► queues + agent
                                   plan·LTV·churn·renewal   0-100 + reasons    auto KB / L1 / L2 / L3
                                                                            ▲
                                    background re-scorer (every 30 s): ageing + SLA-risk ramp
                                                                            │
                         live events (SSE) ──► customer · Level 1-3 agents · admin dashboards
```

**Priority** = 100 × (0.25 frustration + 0.25 urgency + 0.30 value + 0.20 wait/reply-by time), plus rule boosts. The weights and the urgency of each problem type were tuned on training data (`python -m eval.tune_weights`), not copied:
- **+15** for a third contact within 7 days.
- **+10** when renewal is under 14 days and the tone is negative.
- **Up to +50** from 75% of the SLA onward, applied to queue order only, so tickets are served before they breach.

**Routing rules** (three levels):
1. Critical flag → Level 3 (legal also notifies a manager).
2. Confident KB match on a calm, routine question → auto-answer.
3. High frustration → Level 3.
4. High-value customer with score ≥ 50 → Level 3.
5. Score ≥ 65 → Level 3.
6. Technical problem detected, or a technical category → Level 2.
7. Anything else (general categories) → Level 1.

Afterwards a ticket only moves **up**: through ageing, customer replies, "didn't help" feedback, or an agent's **Escalate**.

**Frustration** combines four interpretable signals: negative tone, anger and sarcasm, exclamation marks, and threats to leave (capital letters are deliberately not counted: tested, no accuracy loss). A logistic regression fitted on the training split weights them, and the "high frustration" cut-off is picked by cross-validation to favour recall. If the models are missing, slow (> 3 s) or still loading, every request falls back to the rules engine automatically.

## Run it

**You need PostgreSQL** (the only database, locally and online): create a `triage` user and database and put its address in `backend/.env` as `DATABASE_URL` (step-by-step in [docs/HOW-TO-RUN-AND-TEST.md](docs/HOW-TO-RUN-AND-TEST.md)).

**Windows, one command:**
```powershell
powershell -ExecutionPolicy Bypass -File .\start-demo.ps1
```
The first run creates the environment and downloads the AI models (about 1-2 GB). Add `-Reset` to reseed the demo data.

**Docker:** `docker compose up --build` (starts its own PostgreSQL too), then open http://localhost:5173 (API docs at http://localhost:8000/docs). The image bakes in the models, so it runs offline.

**Manual:**
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
cp .env.example .env                  # then set DATABASE_URL to your PostgreSQL database
python -m scripts.reset_demo        # fresh demo database (42 realistic tickets + demo accounts)
uvicorn app.main:app --port 8000 --timeout-graceful-shutdown 3

cd ../frontend && npm ci && npm run dev    # http://localhost:5173
```
Without the ML packages, set `NLP_MODE=rules` in `.env`; everything still works.

**Accounts:**
- `reset_demo` and `seed` create one admin, one agent per level and four customers (`*@triage.demo`).
- Each install gets **random passwords**, saved in `backend/demo_accounts.local.json`. That file is git-ignored, so passwords never reach GitHub.
- Anyone else can sign up as a customer; an admin then promotes agents under **Users & roles**.
- For anything public, set `SEED_DEMO_ACCOUNTS=false` and a strong `SECRET_KEY`.

**Google sign-in (optional, about 5 minutes):**
1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create (or pick) a project.
2. Open **APIs & Services → OAuth consent screen**: choose *External* and fill in the app name and your email. While testing, add yourself under *Test users*.
3. Open **Credentials → Create credentials → OAuth client ID**:
   - Type: *Web application*.
   - Authorised JavaScript origins: `http://localhost:5173` (plus your deployed URL, if any).
4. Copy the **Client ID** into `backend/.env` as `GOOGLE_CLIENT_ID=...` and restart the backend.

The "Continue with Google" button appears on the login and sign-up pages. New Google users choose their plan once. A Client ID is not secret, but don't commit `.env` anyway; it also holds `SECRET_KEY`.

**Forgot password (no email needed):**
1. **Recovery code:** every new account is shown a one-time code (e.g. `K7QX-2MPD-9RTA`) to save.
   - On *Forgot password? → I have my recovery code*, the customer enters email + code + a new password and immediately gets a fresh code.
   - Anyone can create a new code under **Account & security**.
2. **Lost the code:** *Forgot password? → I lost my code* sends a request to the admin's **Users & workload** page. The admin clicks **Create reset link** (one-time, 30 minutes) and gives the link to the person.

**Tests and evaluation:**
```bash
cd backend
pytest                        # 188 tests in a throwaway PostgreSQL schema (never touches your data)
python -m eval.run_all        # refit, re-tune, re-evaluate, write eval/report.json
```

## Demo script (4 minutes)

Use two browser windows, one normal and one private, so two people are signed in at once: the customer, and the agent or admin.

| Time | Do | Say |
|---|---|---|
| 0:00 | **Admin → Overview**, flip the queue to **Before · arrival order** | "This angry enterprise customer is #15 in line behind password resets." |
| 0:30 | Flip to **After · Priority**; submit the **Outage** example | "Frustration, urgency and value become one score: straight to Level 3 experts." |
| 1:00 | Customer window: **New ticket → How-to**, "How do I reset my password?" | "Routine questions get an instant answer: 96% correct on unseen questions." |
| 1:30 | Customer: new **How-to** ticket, then reply angrily in the chat | Show the toast, the chime in the Level 3 window, and the ticket jumping from Level 1 to Level 3 live. |
| 2:15 | Level 3 window: open it, reply in **live chat**; the customer requests a **call**; mark it scheduled | "Experts can talk to the customer in real time." |
| 2:45 | Admin → **Tuning**: drag the sliders | "Change the weights and watch the queue re-rank live. Nothing is saved." |
| 3:15 | Admin → **Insights** | "On a busy day: urgent waits −32%, high-value −84%, late replies 11 → 0. The ablation shows why every signal matters." |
| 3:45 | Close | "The right person, for the right ticket, right now." |

Before demo day:
- Run `.\start-demo.ps1 -Reset` so wait times look realistic.
- Set `HF_HUB_OFFLINE=1` in `backend/.env` so nothing touches the venue Wi-Fi.

## API

| Method | Path | Who | Purpose |
|---|---|---|---|
| POST | `/api/auth/signup` · `/login` · `/google` · `/logout` | anyone | Accounts (session cookie) |
| GET/PATCH | `/api/auth/me` | signed in | Current user; customers can change plan |
| GET/PATCH | `/api/admin/users[/{id}]` | admin | Roles, plans, enable/disable |
| GET | `/api/categories` | anyone | Ticket categories and their starting level |
| POST | `/api/tickets` | customer, admin | Submit and score a ticket |
| GET | `/api/my/tickets[/{id}]` | customer | Own tickets (no internal scores) |
| GET | `/api/tickets?view=queue\|mine\|resolved` | agents, admin | Level queue / assigned / resolved (admin: all) |
| GET | `/api/tickets/{id}` | agents, admin | Ticket with full explanation |
| POST | `/api/tickets/{id}/claim` · `/escalate` · `/resolve` | agents (own level), admin | Work the ticket |
| POST | `/api/tickets/{id}/override` | admin | Change level and/or priority (locks it) |
| GET/POST | `/api/tickets/{id}/messages` · `/typing` | ticket participants | Conversation / live chat |
| GET/POST/PATCH | `/api/tickets/{id}/callbacks` | customer (request), Level 3 (manage) | Callback requests |
| POST | `/api/tickets/{id}/feedback` | customer | Auto-answer helped / didn't help |
| GET | `/api/events` | signed in | Live events (server-sent events), filtered per role |
| POST | `/api/auth/recover` · `/api/auth/forgot` · `/api/auth/reset` | anyone | Reset with recovery code · ask an admin for help · use an admin's one-time link |
| POST | `/api/auth/me/recovery-code` · `/api/admin/users/{id}/reset-link` | signed in · admin | New recovery code · create a one-time reset link |
| PATCH | `/api/auth/me/availability` | agents | Available / busy / offline |
| GET | `/api/search?q=` | signed in | Role-scoped search: articles, tickets, customers, users |
| POST | `/api/tickets/{id}/attachments` · `/messages/upload` | ticket participants | Upload PNG/JPG/PDF (ticket or chat message) |
| GET | `/api/attachments/{id}` | ticket participants | Download (404 for anyone who can't see the ticket) |
| GET | `/api/tickets/{id}/suggested-reply` · `/guides` | agents, admin | Draft reply · internal guides for this ticket |
| GET/POST/PATCH/DELETE | `/api/kb-articles` · `/api/kb/suggest` · `/api/kb/topics` | all / admin edits | FAQ + guides, "might help" suggestions, suggested topics |
| GET/POST | `/api/incidents[/suggestions]` · `/{id}/reply` · `/{id}/resolve` | agents, admin | Group duplicates, reply to all, resolve all |
| GET | `/api/admin/analytics` · `/users/workload/summary` | admin | Analytics over time · agent workload |
| GET/POST | `/api/admin/retrain` · `/retrain/apply` | admin | Propose / apply thresholds learned from agents |
| GET | `/api/stats` · `/config` | staff | Queue metrics, live configuration |
| GET/POST | `/api/eval` · `/whatif` · `/admin/rescore` | admin | Evaluation report, what-if preview, re-score |

## Project layout

```
backend/app/nlp/        rules.py (flags, intent, signals) · hf.py (models) · analyzer.py · kb.py · frustration_model.py
backend/app/            auth.py (passwords, sessions, roles) · events.py (live events) · categories.py
backend/app/services/   value.py · priority.py · router.py · triage.py · rescore.py
backend/eval/           train_frustration · evaluate_nlp · evaluate_kb · simulate (+ablation) · run_all → report.json
backend/data/           customers.json (20) · kb_articles.json (26) · tickets_labelled.csv (384) · kb_eval.csv · tickets_seed.csv
frontend/src/pages/     auth · customer · agent · admin pages (React Router)
frontend/src/           components (Nordic bento tiles, live chat, queue), lib (auth, live events), light/dark
```

## Honest limitations
- **The evaluation data is synthetic** and written by the team, following a written labelling guide.
  - The test split holds out whole templates and tone phrases, but real tickets would need re-tuning.
  - On this data the transformer models mainly improve **urgency** on harder wording (F1 0.86 AI vs 0.96 rules on our synthetic test set, where the tuned rules fit the templates well) and KB coverage (auto-answers 44% → 78% of routine questions). Frustration is driven mostly by the anger and sarcasm cues, which the fitted weights show openly.
- **Customer value uses mock CRM data.**
- **Accounts are hackathon-grade:**
  - **In place:** hashed passwords, signed HttpOnly cookies, failed-login throttling, role checks, and password reset by recovery code or admin link.
  - **Still missing:** email verification, multi-factor authentication and audit logging.
- **Live chat and events run in one API process.** Several API servers would need a shared message bus such as Redis.
- **Calls are callback requests, not in-browser voice.**
- **No email of any kind, two-factor login or encryption at rest** (decided out of scope). Attachments are stored on local disk.
- **Out of scope:** real CRM integration and production scaling (see roadmap).

## Roadmap
- **Next 2 weeks:**
  - Fine-tune an urgency classifier on real tickets.
  - Retrain the weights from agent overrides, which are already logged as feedback.
- **Next 2 months:**
  - Zendesk / Freshdesk / Salesforce integration.
  - Email and WhatsApp intake.
  - Suggested replies for agents.
- **Later:** voice transcripts, churn prediction from ticket history, workload forecasting.

## Credits
- **Models:**
  - [cardiffnlp/twitter-roberta-base-sentiment-latest](https://huggingface.co/cardiffnlp/twitter-roberta-base-sentiment-latest)
  - [j-hartmann/emotion-english-distilroberta-base](https://huggingface.co/j-hartmann/emotion-english-distilroberta-base)
  - [sentence-transformers/all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)

  See each model card for its licence.
- **Libraries:** FastAPI, SQLAlchemy, scikit-learn, Hugging Face Transformers, React, Vite, Tailwind CSS, lucide-react.
