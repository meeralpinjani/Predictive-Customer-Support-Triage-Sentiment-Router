# Frontend: Support Triage Router

React 18 + React Router + Vite + Tailwind. Nordic palette with semantic light/dark tokens (`src/index.css`) and bento-grid layouts.

```bash
npm ci
npm run dev        # http://localhost:5173 (proxies /api to the backend on :8000)
npm run build      # outputs dist/ (served by nginx in Docker, which also proxies /api)
```

Pages by role, with sidebar navigation on desktop and a bottom tab bar on phones:

| Role | Pages |
|---|---|
| Customer | `/support` (my tickets) · `/support/new` (category picker) · `/support/tickets/:id` (status tracker, conversation / live chat, instant answers, callback request) |
| Level 1-3 agents | `/queue` (level queue, assigned to me, resolved, live activity) · `/tickets/:id` (live chat, claim / escalate / resolve, callbacks, full score explanation) · `/knowledge` |
| Admin | `/admin` (all queues, submit as any CRM customer, what-if) · `/admin/insights` · `/admin/users` · `/admin/tuning` · `/knowledge` |
| Everyone | `/login` · `/signup` (with plan) · `/welcome` (plan picker for new Google users) |

- **Live updates:** one server-sent-events stream per user (`src/lib/events.jsx`) drives toasts, the notification bell, the escalation chime, typing indicators and instant queue refreshes.
- **Session:** an HttpOnly cookie, kept same-origin through the `/api` proxy.
