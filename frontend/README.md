# Frontend: Support Triage Router dashboard

React 18 + Vite + Tailwind, Nordic palette (`tailwind.config.js`) in a bento-grid layout.

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # outputs dist/
```

The API base URL comes from `VITE_API_URL` (default `http://localhost:8000`). See `.env.example`.

## Layout

| Row | Tiles |
|---|---|
| 1 | Live triage hero (open tickets by route) · Deflection rate · Wait time (avg / p95) |
| 2 | Submit a ticket (with playbook example tickets) · Live queue (route tabs, Before FCFS / After Priority toggle, "Arrived #n · #m") |
| 3 | Ticket detail (signals → points, reasons, KB, override, resolve, KB feedback) · Route mix · Avg wait by plan |
| 4 | FCFS vs priority simulation (`/api/simulation`) · KB match tester |
| 5 | Scoring formula + routing ladder (`/api/config`) · Trust & health |

`dist_legacy/` holds the previous compiled UI (its source was lost); it can be deleted once this one is accepted.
