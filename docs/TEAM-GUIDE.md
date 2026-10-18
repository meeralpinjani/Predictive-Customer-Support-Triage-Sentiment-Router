# Support Triage Router: team guide

**Team AlgoAmigos · HelloWorld KIT '26**
*Everything you need to understand, demo and answer questions about the app, with no code knowledge required.*

---

## 1. The idea in one minute

Most support teams answer tickets **first come, first served**. So a furious enterprise customer whose system is down waits behind someone asking how to download an invoice.

Our app **reads every ticket the moment it arrives** and asks three questions:
1. **How frustrated is the customer?** Angry words, sarcasm, CAPITALS, "we'll cancel"…
2. **How urgent is it?** Outage, security, money lost, deadlines…
3. **How valuable is the customer?** Plan, lifetime value, renewal date, churn risk.

It combines those into **one priority score from 0 to 100**, explains *why*, and sends the ticket to the right place:

| Where | Who handles it |
|---|---|
| **Answered automatically** | Simple questions ("How do I reset my password?") get an instant help-centre answer, with no agent needed |
| **Level 1 · General Support** | Accounts, billing, plans, how-to questions |
| **Level 2 · Technical Support** | Bugs, outages, integrations, data, slowness |
| **Level 3 · Expert Escalation** | Critical problems, angry or high-value customers, anything escalated; includes live chat and callback requests |

Tickets **move up live**. If a customer gets angrier in the chat, a ticket waits too long, or an agent clicks **Escalate**, it jumps to the next level within a second, and everyone involved is notified.

---

## 2. Who uses it, and what they see

### Customers
- **Sign up** with email + password (or Google) and pick their plan (Free / Basic / Pro / Enterprise). They receive a **recovery code** for forgotten passwords.
- **New ticket:** choose a category, describe the problem, add screenshots/PDFs. While they type, **"These articles might help"** suggests answers, so many never need a ticket.
- **Ticket page:**
  - A tracker showing General → Technical → Expert, with the agent's first name.
  - The conversation, with file attachments.
  - "Did this help?" on instant answers.
  - **Request a call** once the ticket reaches Level 3.
- **Help centre:** a searchable FAQ.
- **Search bar:** their own tickets and help articles.
- Customers **never see internal scores** or other customers' data.

### Agents (one or more per level)
- **My queue:** their level's tickets, highest priority first. A **Before/After** switch shows the old first-come order versus ours.
- **Ticket workspace:**
  - Live chat with attachments.
  - **Suggest reply:** drafts an answer with the right tone for the customer's mood.
  - **Guides for this ticket:** e.g. the security runbook pops up on a hacked-account ticket.
  - Claim / Escalate / Resolve.
  - The full explanation of the score.
- **Availability:** Available / Busy / Offline. Busy or offline agents get no new tickets; their waiting tickets go to colleagues.
- **Incidents:** when many customers report the same problem (e.g. an outage), the app suggests grouping them. One reply or "resolve" covers everyone.
- **Knowledge base:** public help articles and internal guides.

### Admin
- **Overview:** all queues live, a submit-a-test-ticket form, the score explanation and **what-if** sliders.
- **Analytics:** tickets per hour, % answered automatically, escalations, response and resolution times, all from real data.
- **Insights & proof:** how accurate the AI is on tickets it never saw, and the busy-day simulation.
- **Users & workload:**
  - Promote sign-ups to agents.
  - Set each agent's capacity.
  - See everyone's load.
  - Handle password-help requests.
- **Knowledge-base editor:** write or edit articles and guides; it suggests **new topics** from questions nothing could answer.
- **Tuning:** try other weights safely; **retrain** routing from agents' decisions once 30+ exist.
- **Integrity** (optional, off by default): a review aid that points out tickets worth a human look. See below.

### Summaries and handovers (everyone)
- **View summary** on every ticket: a short digest built only from saved messages, where every quoted line shows which message it came from. It's marked *Up to date* or *Out of date*, and **View full conversation** is always one click away. **The conversation is the truth; the summary just makes it quicker to read.** Customers see a simpler version without internal notes.
- **Handover:** when a ticket moves to another level or agent, the next agent sees a box above the reply field: why it moved, what was tried, what's confirmed, what's still to do and what was promised. It's frozen at that moment and can't be edited. "Built from raw messages" means the summary wasn't available, so read the conversation.
- **Connection drops:** messages show *Sending… / Not sent – Retry*, never "saved" before the server confirms. A retry can't create a duplicate, unsent text survives a refresh, and an expired session brings you back to the same ticket after signing in.

### Integrity review aid (admins only)
**What it does.** After a customer creates a ticket, replies or uploads a PDF/DOCX, it quietly checks four things in the background:
1. **Writing patterns:** does the text look AI-written? (a free, local detector model; English only)
2. **Near-identical tickets:** the same text sent again, by the same or another customer.
3. **Our own records:** e.g. "this is my first time contacting you" when ticket history shows earlier tickets; a plan named that differs from the plan on file. Payment claims can't be checked: we hold no payment records.
4. **Clear warning signs:** repeated requests to skip checks or verification, or text giving instructions to an automated system.

Clear signs suggest a **manual review**. AI-like writing **alone never does**, because using ChatGPT or a translator to write a complaint is legitimate.

**What it can't prove.** It never decides fraud. The detector is wrong on formal, templated or non-native English, it can't read Hinglish, and its score is **not a probability**. A person must always check the evidence, and confirming a concern requires a written reason that is logged with the reviewer's name.

**What it never does.** It never changes priority, reply-by times, levels, emergencies, the assigned agent or what customers see; it never slows down or blocks a customer; agents and customers can't see it at all.

---

## 3. How the "AI" works (plain words)

1. **Reading the text.** Two pretrained AI models run **on our laptop**, free and offline:
   - one reads **tone** (negative sentiment, anger);
   - one understands **meaning** (what kind of problem, which help article fits).

   Rule checks run alongside them:
   - **Critical words, with negation:** "we were *not* hacked" does **not** trigger a security alarm.
   - **Sarcasm:** "Great, just great. Thanks for nothing".
   - **Exclamation marks (!!!, ??) and threats to cancel.** Capital letters are *not* counted: people type in capitals for many calm reasons, and the data showed no loss without them.
   - **Hinglish:** "Mera payment fail ho gaya".
2. **Frustration score:** combines four signals (negative tone, anger/sarcasm, exclamation marks, threats to leave). The weights were **learned from labelled data**, not guessed.
3. **Priority:** `25% frustration + 25% urgency + 30% customer value + 20% waiting time` (tuned on training data in a simulated busy day, not guessed), plus small boosts:
   - **+15** for a third contact in a week.
   - **+10** when the renewal is near and the customer is unhappy.
   - **Up to +50** as a ticket approaches its SLA deadline, so **nobody is forgotten**.
4. **Routing:**
   - Critical issues, high frustration, valuable accounts or very high scores → Level 3.
   - Technical problems → Level 2.
   - Everything else → Level 1.
   - A confident help-centre match on a calm, simple question → answered automatically.

   The category a customer picks is a **starting point**: the AI can move a ticket up, never down.
5. **Safety net:** if the AI models are missing or slow, the app keeps working on its rules engine automatically.

---

## 4. The numbers (for the pitch)

Measured on **132 tickets the system never saw while being tuned**:

| What | Target | Ours |
|---|---|---|
| Urgency classification (F1) | ≥ 0.75 | **0.86** |
| Catches highly frustrated customers (recall) | ≥ 0.80 | **0.83** (precision 0.94) |
| Tickets sent to experts that truly needed it | ≥ 0.80 | **0.97** |
| Critical issues caught (security, legal, safety, outage) | n/a | **100%** |
| Automatic answers that were correct | ≥ 0.90 | **0.96** |
| Speed per ticket | < 2 s | **~0.2 s** |

**A simulated busy day** (120 tickets, 3 agents, demand ~30% above capacity), compared with first-come-first-served:
- Urgent tickets wait **32% less**.
- High-value customers wait **84% less**.
- Late replies drop from **11 to 0**.

**The honest trade-off:** routine tickets from free customers wait a bit longer, but within their 8-hour promise.

---

## 5. Demo plan (4 minutes, 3 windows)

Open **Admin**, the **Level 3 agent** and a **customer** (private window).

1. **Admin → Overview:** flip the queue to *Before · arrival order*, then *After · Priority*. "The angry enterprise outage jumps from #15 to the top."
2. **Customer:** ask "How do I reset my password?". It's answered instantly: "96% of instant answers are correct."
3. **Customer:** open a calm ticket, then reply angrily in the chat. **Watch it jump to Level 3 live**; the expert's window chimes.
4. **Level 3:** open it, click **Suggest reply**, send; the customer **requests a call** and the expert schedules it.
5. Show the **Hinglish**, **sarcasm** and **"not hacked"** examples (admin Overview → example buttons).
6. **Admin → Analytics** and **Insights:** the numbers above.
7. Close: *"The right person, for the right ticket, right now."*

---

## 6. Likely judge questions

| Question | Answer |
|---|---|
| *What if the AI is wrong?* | Every score is explained. Agents can escalate, admins can override, and those decisions feed **Retrain**. Critical issues use deterministic rules, never a guess. |
| *Is prioritising VIPs unfair?* | Value is only 25% of the score. Security, safety and angry customers escalate whatever their plan, and the SLA boost guarantees nobody waits forever. |
| *How is it different from Zendesk?* | One transparent score, explanations, live escalation, measured impact, and it runs free and offline. |
| *Does the data leave the machine?* | No. The AI models run locally; nothing is sent to paid APIs. |
| *How did you measure?* | 384 labelled tickets, split so the test sentences were never seen during tuning, plus a reproducible simulation (`python -m eval.run_all`). |
| *What about sarcasm and other languages?* | Sarcasm cues are part of the frustration model; Hinglish is understood for common phrases. Full multilingual support is on the roadmap. |
| *Security?* | Hashed passwords, signed HttpOnly sessions, role checks on every request, private attachments checked by real file type, throttled logins, password recovery without email. |

---

## 7. What's under the hood

| Part | Technology |
|---|---|
| Backend | Python, FastAPI, PostgreSQL (SQLAlchemy) |
| AI | Hugging Face models: RoBERTa sentiment and emotion, MiniLM embeddings; scikit-learn |
| Frontend | React, Vite, Tailwind CSS (Nordic look, light/dark) |
| Live updates | Server-sent events |
| Sign-in | Email/password (scrypt), Google sign-in, recovery codes |
| Tests | 188 automated tests (pytest) on PostgreSQL |

**Folders:** `backend/` (API, AI, tests, evaluation), `frontend/` (the website), `docs/` (this guide and the run checklist), `start-demo.ps1` (one-command start).

---

## 8. Known limits (say them before the judges do)

- The evaluation tickets are **synthetic**, written by the team using a written labelling guide. Real company data would need re-tuning.
- Customer value uses **mock CRM data**.
- No email (password recovery uses codes or admin links), no two-factor login, no encryption at rest.
- Calls are **callback requests**, not in-browser voice.
- Built for one server; scaling out would need a shared message bus.

---

## 9. How to run it

See **[HOW-TO-RUN-AND-TEST.md](HOW-TO-RUN-AND-TEST.md)**. Short version: `powershell -ExecutionPolicy Bypass -File .\start-demo.ps1 -Reset`, then open http://localhost:5173. Demo passwords are in `backend/demo_accounts.local.json` on the laptop that ran the setup. For every technical detail (sentiment analysis, scoring, suggested reply, security) see **[TECHNICAL-DEEP-DIVE.md](TECHNICAL-DEEP-DIVE.md)**.
