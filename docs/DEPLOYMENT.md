# Deploying for free

| Part | Host | Free tier |
|---|---|---|
| Backend (FastAPI + AI models) | **Hugging Face Spaces** (Docker) | CPU Basic: 2 vCPU, 16 GB RAM, enough for the full AI |
| Database | **Neon** (PostgreSQL) | ~0.5 GB, scales to zero when idle |
| Frontend (React) | **Vercel** | Hobby plan |

```
Browser ──► Vercel (React app)
              └─ /api/* rewritten to ──► Hugging Face Space (FastAPI + models) ──► Neon PostgreSQL
```

The browser only ever talks to the Vercel address; Vercel forwards `/api` to the Space. That keeps the sign-in cookie on one site, so login works without cross-site cookies.

Free tiers change; check each provider's pricing page. You need three free accounts: Neon, Hugging Face and Vercel (sign in with GitHub where offered).

---

## 1. Database: Neon

1. Sign up at https://neon.tech and create a project (pick the region closest to you, e.g. Singapore or Frankfurt).
2. On the dashboard click **Connect**, turn **Connection pooling off**, and copy the connection string. It looks like:
   `postgresql://neondb_owner:...@ep-xxxx.region.aws.neon.tech/neondb?sslmode=require`
3. Keep it private: it is the database password. You'll paste it into Hugging Face in step 2.

> Use the **direct** (non-pooled) string. The backend keeps its own small connection pool, and the pooled endpoint doesn't work well with the driver's prepared statements.

The backend creates all tables and the demo data by itself on first start.

---

## 2. Backend: Hugging Face Space

### 2.1 Create the Space
1. Sign up at https://huggingface.co.
2. **New → Space**:
   - Space name: e.g. `triage-router`
   - SDK: **Docker** → **Blank**
   - Hardware: **CPU basic (free)**
   - Visibility: **Public** (Vercel must be able to reach it; secrets stay hidden)
3. Open the Space → **Settings → Variables and secrets** and add:

| Type | Name | Value |
|---|---|---|
| Secret | `DATABASE_URL` | the Neon connection string |
| Secret | `SECRET_KEY` | a long random string: `python -c "import secrets; print(secrets.token_urlsafe(32))"` |
| Secret | `DEMO_PASSWORD` | password for the demo agents and customers |
| Secret | `DEMO_ADMIN_PASSWORD` | a different, stronger password for `admin@triage.demo` |
| Variable | `COOKIE_SECURE` | `true` |
| Variable | `CORS_ORIGINS` | your Vercel address (step 3), e.g. `https://triage-router.vercel.app` |
| Secret | `GOOGLE_CLIENT_ID` | optional: your Google client ID |
| Variable | `ADMIN_EMAIL` | optional: this email becomes admin when it signs up |
| Variable | `AI_INTEGRITY_ENABLED` | optional: `true` turns on the admin Integrity review aid (the detector model is already inside the image) |

### 2.2 Push the code (automatic)
The repository has a workflow (`.github/workflows/deploy-backend.yml`) that pushes the `backend/` folder to the Space on every push to `main`.

1. Hugging Face → profile picture → **Settings → Access Tokens → Create new token**, type **Write**. Copy it.
2. GitHub repository → **Settings → Secrets and variables → Actions**:
   - **Secrets** tab → *New repository secret*: `HF_TOKEN` = the token
   - **Variables** tab → *New repository variable*: `HF_SPACE` = `<your-hf-username>/<space-name>`, e.g. `meeralpinjani/triage-router`
3. GitHub → **Actions → Deploy backend to Hugging Face → Run workflow**. After that it runs by itself whenever `backend/` changes.

**Or push by hand** (from the project folder; use the token as the password):
```bash
git push --force https://huggingface.co/spaces/<hf-username>/<space-name> "$(git subtree split --prefix backend HEAD):refs/heads/main"
```

### 2.3 Wait for the build
The Space builds the Docker image: installing PyTorch and downloading the models takes about **10–20 minutes** the first time. The **Logs** tab shows progress. When it says *Running*:

- Your backend address is `https://<hf-username>-<space-name>.hf.space`
- Check `https://<hf-username>-<space-name>.hf.space/api/health` shows `"db": "ok"` and, after ~30 s, `"models": "ready"`.
- API docs are at `/docs` on the same address.

---

## 3. Frontend: Vercel

1. Edit [`frontend/vercel.json`](../frontend/vercel.json): replace `YOUR-SPACE-SUBDOMAIN` with your Space address, e.g.
   ```json
   { "source": "/api/:path*", "destination": "https://meeralpinjani-triage-router.hf.space/api/:path*" }
   ```
   Commit and push.
2. Sign up at https://vercel.com with GitHub → **Add New → Project** → import the repository.
3. **Root Directory: `frontend`**. Framework preset: **Vite** (detected). Leave build settings as they are.
4. **Deploy.** You get an address like `https://triage-router.vercel.app`.
5. Put that address in the Space's `CORS_ORIGINS` variable (step 2.1).

Every push to `main` redeploys the frontend automatically.

---

## 4. Google sign-in (optional)

Google Cloud Console → **APIs & Services → Credentials** → your OAuth client → **Authorised JavaScript origins** → add the Vercel address. Make sure `GOOGLE_CLIENT_ID` is set in the Space and restart it (**Settings → Restart**).

---

## 5. Check it

1. Open the Vercel address and sign in as `admin@triage.demo` with `DEMO_ADMIN_PASSWORD`.
2. Agents and customers (`level1@`, `level2@`, `level3@`, `northwind@`, `priya@`, `ravi@`, `elena@triage.demo`) use `DEMO_PASSWORD`.
3. Open a private window as a customer, create a ticket, and watch it appear live in the agent's queue.
4. Follow [HOW-TO-RUN-AND-TEST.md](HOW-TO-RUN-AND-TEST.md) for the full checklist.

---

## Good to know

| Topic | Detail |
|---|---|
| **Sleeping** | A free Space sleeps after about 48 hours without visitors. Opening the site wakes it in 1–2 minutes (models load). Open it a few minutes before judging. |
| **Neon idle** | The database pauses when idle and wakes on the first request (about a second). |
| **Live updates** | Work through Vercel; if a proxy closes a long connection, the browser reconnects automatically within 3 s. |
| **Files** | Attachments are stored in PostgreSQL, so they survive restarts. |
| **Retraining** | Accepted router tuning is stored in the database too. |
| **Fresh demo data** | From your laptop, with the Neon URL: `$env:DATABASE_URL="<neon url>"; python -m scripts.reset_demo` (in `backend`, venv active). **This wipes the hosted database.** |
| **Passwords** | Changing `DEMO_PASSWORD` / `DEMO_ADMIN_PASSWORD` and restarting the Space updates the demo accounts. |
| **Local development** | Also PostgreSQL (see HOW-TO-RUN-AND-TEST.md), so local and deployed behave the same. |

## Troubleshooting

| Problem | Fix |
|---|---|
| Space build fails | Read the **Logs** tab; most often a typo in a secret name. Rebuild with **Settings → Factory rebuild**. |
| Space shows *Runtime error*, logs mention the database or `connection` | `DATABASE_URL` is wrong or missing `?sslmode=require`, or the pooled Neon string was used. Copy the direct one again and restart. |
| Site loads but every request fails | `vercel.json` still has `YOUR-SPACE-SUBDOMAIN`, or the Space is private or asleep. |
| Signed out after every refresh | `COOKIE_SECURE` must be `true` and the site opened via `https://`. |
| Everyone signed out after a restart | `SECRET_KEY` isn't set, so a new one is generated each start. |
| Google: `origin_mismatch` | Add the exact Vercel address to Authorised JavaScript origins. |
