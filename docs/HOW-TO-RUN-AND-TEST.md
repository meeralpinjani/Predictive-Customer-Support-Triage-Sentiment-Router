# How to run and check everything

A step-by-step checklist. Follow it top to bottom once before the demo; it touches every feature.

---

## 1. Start the app

**Windows, one command** (from the project folder):
```powershell
powershell -ExecutionPolicy Bypass -File .\start-demo.ps1 -Reset
```
- The **first run** installs everything and downloads the AI models (about 1–2 GB, 5–10 minutes).
- `-Reset` gives you a **fresh demo database**: 23 realistic tickets plus the demo accounts. Leave it off to keep your data.
- It opens two terminal windows (backend and frontend) and the browser at **http://localhost:5173**.

**Without the script:**
```bash
# terminal 1
cd backend
.venv\Scripts\activate
python -m scripts.reset_demo        # optional: fresh demo data
uvicorn app.main:app --port 8000

# terminal 2
cd frontend
npm run dev                          # http://localhost:5173
```

**Wait about 30 seconds after starting.** The AI models load in the background. Until then the app uses its rules engine, and the sidebar or health check shows "AI models loading…".

---

## 2. Sign in

**Demo accounts:** all are `@triage.demo`. Their passwords were generated for your machine and are in `backend/demo_accounts.local.json`, which is never uploaded to GitHub.

| Email | Role | Use it to show |
|---|---|---|
| `admin@triage.demo` | Admin | Everything: overview, analytics, users, knowledge-base editor |
| `level1@triage.demo` | Level 1 · General Support (Astrid) | Account, billing, how-to tickets |
| `level2@triage.demo` | Level 2 · Technical Support (Ingrid) | Bugs, outages, integrations |
| `level3@triage.demo` | Level 3 · Expert Escalation (Magnus) | Critical and escalated tickets, live chat, calls |
| `northwind@triage.demo` | Customer · Enterprise | High-value customer |
| `priya@triage.demo` | Customer · Pro | Normal customer |
| `ravi@triage.demo` | Customer · Basic (Hinglish) | Hinglish tickets |
| `elena@triage.demo` | Customer · Free | Free-plan customer |

**Tip:** use one normal window and one **private/incognito** window to be two people at once (e.g. a customer and an agent). Live updates then appear between them.

---

## 3. Checklist by feature

Tick each one. Expected results are in *italics*.

### Accounts and sign-in
- [ ] **Sign up:** on `/signup` create a new customer and pick a plan. *After creating, a recovery code like `K7QX-2MPD-9RTA` is shown; "Go to my tickets" only unlocks after ticking "I've saved it".*
- [ ] **Password rules:** try a weak password. *A live checklist shows 8+ characters, upper case, lower case and a number.*
- [ ] **Wrong password:** *a "We couldn't sign you in" message.*
- [ ] **Remember me:** unticked means you're signed out when the browser closes; ticked keeps you signed in for 7 days.
- [ ] **Google:** *"Continue with Google" shows under "OR"* (needs `GOOGLE_CLIENT_ID` in `backend/.env`). New Google users pick a plan once.
- [ ] **Forgot password with code:** go to *Forgot password? → I have my recovery code*, enter the code and a new password. *The password changes and a new code is shown (the old one stops working).*
- [ ] **Forgot password without code:** go to *I lost my code* and enter the email. Sign in as admin → **Users & workload**. *A "Password help" box lists the request; **Create reset link** gives a one-time link (30 min) to copy and hand over.* Open the link → set a new password.
- [ ] **Account & security** (link under your name in the sidebar): *create a new recovery code (asks for your current password).*

### Customer side (e.g. Priya)
- [ ] **Home:** *stat cards (open / in progress / resolved / answered instantly), recent tickets, quick help articles.*
- [ ] **New ticket:** pick a category and start typing "my credit card expired…". *"These articles might help" suggests **Updating Your Payment Method** while you type.*
- [ ] **Attach files:** drag in a PNG/JPG/PDF (max 5 files, 5 MB each). *A `.txt`, a renamed file or a file over 5 MB is refused with a clear message.*
- [ ] **Instant answer:** category *Account & login*, "How do I reset my password?". *Answered automatically, with "Did this help? Yes / No, I need a person".* Click **No**: *it goes to a human agent live.*
- [ ] **Ticket page:** *level tracker (General → Technical → Expert), conversation, your files, related help articles.*
- [ ] **Live escalation:** on a calm ticket, reply angrily ("This is RIDICULOUS!!! Fix it NOW or we cancel!"). *Within a second the ticket moves to **Level 3 · Expert Escalation**, the chat turns into "Live chat" and "Request a call" appears.*
- [ ] **Request a call** (Level 3 only): *the expert sees it and can mark it scheduled or done.*
- [ ] **Help centre:** *searchable FAQ grouped by topic.*
- [ ] **Search bar** (top, Ctrl K): type "invoice". *Finds help articles and your own tickets only.*

### Agent side (Level 1–3)
- [ ] **My queue:** *only your level's tickets, sorted by priority, with "Before · FCFS / After · Priority" and a live activity feed.*
- [ ] **Availability:** set yourself **Busy** in the sidebar. *New tickets at your level aren't assigned to you; set **Available** and waiting tickets come back.*
- [ ] **Open a ticket:** *live chat, customer's files, Actions (Claim / Escalate / Resolve), **Guides for this ticket**, and the full score explanation.*
- [ ] **Suggest reply:** *drafts a greeting, empathy matched to the customer's mood, the right article or next step, and a promise based on their SLA. Edit it, then send.*
- [ ] **Attach in chat** (paperclip): *the customer sees the file.*
- [ ] **Escalate:** write a reason, then **Escalate to Level 2/3**. *The ticket leaves your queue; the next level gets a toast and a chime.*
- [ ] **Guides:** open a security ticket ("someone hacked my account"). *The Security runbook shows automatically.*
- [ ] **Incidents:** create 2–3 similar tickets from different customers ("Slack webhooks stopped arriving"). On **Incidents** → *"Possible duplicates"*, click **Group**, then **Reply to all** and **Resolve all**.
- [ ] **Knowledge base:** *public articles and 🔒 internal guides.*
- [ ] **Search:** *finds articles, internal guides, tickets at your level and those customers.*

### Admin side
- [ ] **Overview:** *every level's queue, submit a test ticket as any CRM customer (with playbook examples), inspect any score, what-if sliders.*
- [ ] **Analytics:** *tickets per hour, deflection, escalations, first-response and resolution time per day (charts or table), from real data only.* It looks thin at first and fills in as you use the app.
- [ ] **Insights:** *AI scorecard on unseen tickets, FCFS vs router simulation, ablation, fitted frustration model.*
- [ ] **Users & workload:**
  - *Each agent's load vs capacity.*
  - *Change a role, plan, capacity or availability.*
  - *Disable a user.*
  - *Create reset links.*
  - *Password-help requests.*
- [ ] **Promote a new agent:** sign up a new account, then set its role to Level 2. *It starts receiving Level 2 tickets.*
- [ ] **Knowledge base editor:**
  - **New article**, public or internal; *it immediately auto-answers matching questions.*
  - Edit or delete articles.
  - *"Suggested new topics" groups questions nothing answered; **Draft an article** pre-fills the form.*
- [ ] **Tuning:**
  - *What-if sliders re-rank the queue without saving.*
  - *Formula and routing ladder.*
  - *KB match tester.*
  - *Trust & health.*
  - **Retrain routing:** *shows "x / 30 agent decisions" until there are enough.*

### Everywhere
- [ ] **Dark mode** (moon icon), **phone size** (bottom tab bar, admin has **More**), **notifications bell**, **toasts**.

---

## 4. Automated checks

```bash
cd backend
.venv\Scripts\activate
pytest                    # 112 tests: AI, routing, roles, security, attachments, escalation, every feature
python -m eval.run_all    # re-runs the whole evaluation (~3 min) and updates the Insights page numbers
```

The tests use a separate temporary database and upload folder, so they never touch your demo data.

---

## 5. Before the demo

1. `.\start-demo.ps1 -Reset` so ticket ages look fresh.
2. Add `HF_HUB_OFFLINE=1` to `backend/.env` so nothing depends on the venue Wi-Fi (models are already cached).
3. Open three windows: **admin**, **Level 3 agent**, **customer** (private window).
4. Have the demo passwords file (`backend/demo_accounts.local.json`) open privately, not on the projector.

## 6. If something goes wrong

| Problem | Fix |
|---|---|
| "Cannot reach the server" / "API offline" | The backend window isn't running; start it (step 1). |
| Sidebar says "Reconnecting…" | Live updates paused; it reconnects by itself. Refresh if it stays. |
| Google button missing | `GOOGLE_CLIENT_ID` not set in `backend/.env`, or the backend wasn't restarted. |
| Google says "origin_mismatch" | Add `http://localhost:5173` under *Authorised JavaScript origins* in Google Cloud. |
| Tickets wait "Unassigned" | No agent at that level is **Available** with free capacity; check **Users & workload**. |
| Strange data after testing | `.\start-demo.ps1 -Reset` (demo passwords stay the same). |
