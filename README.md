# Predictive Customer Support Triage & Sentiment Router

**Team AlgoAmigos · HelloWorld KIT '26**

Support queues answer tickets first come, first served, so a furious enterprise customer whose production is down waits behind someone asking how to download an invoice. This system reads every ticket, measures **frustration**, **urgency** and **customer value**, merges them into **one explainable 0-100 priority score**, and routes the ticket: an instant knowledge-base answer, Tier 1, a Tier 2 specialist, or a senior agent. Waiting time raises priority, so nobody is left behind.

## Results (held-out test set, `python -m eval.run_all`)

| Metric | Target (playbook 13.1) | AI models (default) | Rules fallback |
|---|---|---|---|
| Urgency F1, 3 classes | ≥ 0.75 | **0.84** | 0.78 |
| Frustration recall / precision | recall ≥ 0.80 | **0.83 / 0.94** | 0.83 / 0.94 |
| Escalation precision (sent to Senior that should be) | ≥ 0.80 | **0.97** | 0.97 |
| Critical-issue recall (security, legal, safety, outage) | n/a | **1.00** | 1.00 |
| KB auto-answer accuracy | ≥ 0.90 | **0.96** | 1.00 |
| Safe auto-answers (routine and not angry) | n/a | **0.95** | 0.94 |
| Latency per ticket | < 2 s | **151 ms** | 3 ms |

**A busy simulated day** (120 tickets, 3 agents, demand ≈ 129% of capacity, per-customer SLAs):

| | FCFS | Router | Change |
|---|---|---|---|
| Urgent tickets, avg wait | 62.5 min | **32.3 min** | −48% |
| High-value customers, avg wait | 55.3 min | **16.7 min** | −70% |
| SLA breaches | 11 | **3** | −73% |
| Low-priority tickets, avg wait | 63.8 min | 92.6 min | +45% (within SLA) |
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
                                   plan·LTV·churn·renewal   0-100 + reasons    auto KB / T1 / T2 / Senior
                                                                            ▲
                                    background re-scorer (every 30 s): ageing + SLA-risk ramp
```

**Priority** (playbook 9.1) = 100 × (0.30 frustration + 0.30 urgency + 0.25 value + 0.15 wait/SLA), plus rule boosts (playbook 9.4):
- **+15** for a third contact within 7 days.
- **+10** when renewal is under 14 days and the tone is negative.
- **Up to +50** from 75% of the SLA onward, applied to queue order only, so tickets are served before they breach.

**Routing ladder** (playbook 10.1):
1. Critical flag → Senior (legal also notifies a manager).
2. Confident KB match on a calm, routine question → auto-answer.
3. High frustration → Senior.
4. High-value customer with score ≥ 50 → Senior.
5. Score ≥ 65 → Senior.
6. Score ≥ 40, or a billing / login / technical / cancellation problem → Tier 2 specialist.
7. Anything else → Tier 1.

**Frustration** combines four interpretable signals: negative tone, anger and sarcasm, shouting, and churn threats. A logistic regression fitted on the training split weights them (playbook 9.5), and the "high frustration" cut-off is picked by cross-validation to favour recall. If the models are missing, slow (> 3 s) or still loading, every request falls back to the rules engine automatically.

## Run it

**Windows, one command:**
```powershell
powershell -ExecutionPolicy Bypass -File .\start-demo.ps1
```
The first run creates the environment and downloads the AI models (about 1-2 GB). Add `-Reset` to reseed the demo data.

**Docker:** `docker compose up --build`, then open http://localhost:5173 (API docs at http://localhost:8000/docs). The image bakes in the models, so it runs offline.

**Manual:**
```bash
cd backend
python -m venv .venv && .venv/Scripts/activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
pip install -r requirements-ml.txt --extra-index-url https://download.pytorch.org/whl/cpu
cp .env.example .env
python -m scripts.reset_demo        # fresh demo database (22 realistic tickets)
uvicorn app.main:app --port 8000

cd ../frontend && npm ci && npm run dev    # http://localhost:5173
```
Without the ML packages, set `NLP_MODE=rules` in `.env`; everything still works.

**Tests and evaluation:**
```bash
cd backend
pytest                        # 74 tests, isolated temp database (never touches triage.db)
python -m eval.run_all        # refit, re-tune, re-evaluate, write eval/report.json
```

## Demo script (4 minutes, playbook 15.1)

| Time | Do | Say |
|---|---|---|
| 0:00 | Live tab, flip the queue to **Before · FCFS** | "This angry enterprise customer is #15 in line behind password resets." |
| 0:30 | Flip to **After · Priority**, click **Outage**, then **Score & route** | "Frustration, urgency and value become one score; straight to a senior agent." |
| 1:15 | Open the ticket | "Every point is explained: signals, rule boosts, how the AI read the tone, who it went to." |
| 1:45 | Click **Password**, then submit | "Routine questions never reach an agent: 96% of auto-answers were correct on unseen questions." |
| 2:15 | **Hinglish**, then **Sarcasm**, then **Not hacked** | "Hinglish works, sarcasm is caught, and 'we were not hacked' does not trigger a security escalation." |
| 2:45 | Drag the what-if sliders | "Change the weights and watch the queue re-rank live. Nothing is saved." |
| 3:15 | Insights tab | "On a busy day, urgent waits fell 48%, high-value 70%, SLA breaches 11 → 3. The ablation shows why every signal matters." |
| 3:45 | Close | "Faster help for the customers who need it most, at lower cost." |

Before demo day:
- Run `.\start-demo.ps1 -Reset` so wait times look realistic.
- Set `HF_HUB_OFFLINE=1` in `backend/.env` so nothing touches the venue Wi-Fi.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/tickets` | Submit and score a ticket |
| GET | `/api/tickets?route=&status=&sort=priority\|fcfs` | Queue (read-only) |
| GET | `/api/tickets/{id}` | Ticket with full explanation |
| POST | `/api/tickets/{id}/override` | Agent changes route and/or priority (locks it, logged as feedback) |
| POST | `/api/tickets/{id}/resolve` | Resolve (one-way) |
| POST | `/api/tickets/{id}/feedback` | KB helped / didn't help (didn't help → re-scored and escalated) |
| GET | `/api/stats` | Counts, waits, deflection, override and acceptance rates |
| POST | `/api/whatif` | Preview re-ranking under other weights or thresholds |
| GET | `/api/eval` · `/api/config` · `/api/health` | Evaluation report, live configuration, model status |

## Project layout

```
backend/app/nlp/        rules.py (flags, intent, signals) · hf.py (models) · analyzer.py · kb.py · frustration_model.py
backend/app/services/   value.py · priority.py · router.py · triage.py · rescore.py
backend/eval/           train_frustration · evaluate_nlp · evaluate_kb · simulate (+ablation) · run_all → report.json
backend/data/           customers.json (20) · kb_articles.json (26) · tickets_labelled.csv (384) · kb_eval.csv · tickets_seed.csv
frontend/src/           React + Tailwind, Nordic bento dashboard (Live + Insights tabs, light/dark)
```

## Honest limitations
- **The evaluation data is synthetic** and written by the team, following the playbook's labelling guide.
  - The test split holds out whole templates and tone phrases, but real tickets would need re-tuning (playbook 16).
  - On this data the transformer models mainly improve **urgency** (F1 0.78 → 0.84) and KB coverage (auto-answers 44% → 78% of routine questions). Frustration is driven mostly by the anger and sarcasm cues, which the fitted weights show openly.
- **Customer value uses mock CRM data.**
- **Out of scope:** authentication, real CRM integration and production scaling (playbook "will not do"; see roadmap).

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
