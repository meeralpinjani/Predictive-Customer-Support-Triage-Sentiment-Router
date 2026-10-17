# Frontend: Support Triage Router dashboard

React 18 + Vite + Tailwind. Nordic palette with semantic light/dark tokens (`src/index.css`) and a bento-grid layout.

```bash
npm ci
npm run dev        # http://localhost:5173 (expects the API on :8000)
npm run build      # outputs dist/
```

Set the API address with `VITE_API_URL` (default `http://localhost:8000`, see `.env.example`).

- **Live tab** (`src/components/live/`):
  - Hero queue status, deflection rate, wait times.
  - Ticket form with the playbook's examples.
  - Live queue: Before/After toggle, SLA bars, ↑/↓ keyboard navigation.
  - Ticket detail explaining every point.
  - What-if sliders that re-rank the queue without saving.
- **Insights tab** (`src/components/insights/`):
  - FCFS vs router results (chart and table).
  - Model scorecard against the playbook's targets.
  - Ablation study and the fitted frustration model.
  - Scoring formula and routing ladder.
  - KB match tester, trust metrics and method notes.

Chart colours were checked for colour-blind separation and contrast in both themes.
