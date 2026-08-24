# Hackathon boilerplate (FastAPI) + Workflow Orchestration

Working auth + DB + API skeleton, ready to deploy to Render, with a complete **Fault-Tolerant Multi-System Workflow Orchestration** foundation built on top.

## What's Already Wired Up (Original)

- `POST /api/auth/register` — create a user
- `POST /api/auth/login` — get a JWT access token
- `GET /api/auth/me` — example protected route (needs `Authorization: Bearer <token>`)
- `GET /api/health` — health check
- `GET /docs` — interactive API docs (Swagger UI), auto-generated
- SQLAlchemy models + SQLite locally, swaps to Postgres on Render via `DATABASE_URL`
- Tables auto-create on startup (no Alembic — intentional, see `main.py` comment)
- Global JSON error handler so a crash returns JSON, not an HTML error page

## What's New: Workflow Orchestration Foundation

A complete **structural foundation** for Order → Inventory → CRM → Notification workflow orchestration:

- **Orchestrator engine** — executes multi-step workflows, handles retries, logs events
- **Independent services** — Inventory, CRM, Notification each with own API & database boundary
- **Order entry point** — REST API to create orders and trigger workflows
- **Audit logging** — complete immutable history of all workflow events
- **Step abstraction** — pipeline-oriented workflow definition (not yet fully generic)
- **Retry & idempotency boundaries** — structural support for future fault-tolerance features
- **Transformation layer** — isolates service input/output mapping
- **Vanilla frontend dashboard** — real-time workflow status visualization & execution logs

**See [WORKFLOW_STRUCTURE.md](WORKFLOW_STRUCTURE.md) for detailed architecture & design decisions.**

### Quick Start: Workflow Demo

```bash
cd hackathon-boilerplate
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_hex(32))" > .env  # optional: generate SECRET_KEY

uvicorn app.main:app --reload
```

Then open:
- **API Docs**: http://127.0.0.1:8000/docs
- **Workflow Dashboard**: http://127.0.0.1:8000/static/index.html

Create an order via the dashboard or API:

```bash
curl -X POST http://localhost:8000/api/order/create \
  -H "Content-Type: application/json" \
  -d '{"customer_email": "customer@example.com", "sku": "ITEM-001", "quantity": 5}'
```

Watch the workflow execute through Inventory → CRM → Notification.

---

## Existing Setup (Unchanged)

### 1. Run it locally

```bash
cd hackathon-boilerplate     
pip install -r requirements.txt
cp .env.example .env
```

Generate a real secret key and put it in `.env`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

```bash
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs — you should see the Swagger UI. Try
`/api/health` first (should return `{"status": "ok"}`), then register a user
via `/api/auth/register`, then log in via `/api/auth/login` to get a token.

### 2. Push to GitHub

```bash
git init
git add .
git commit -m "Hackathon boilerplate: auth, db, api scaffold + workflow orchestration"
```

Create a new empty repo on GitHub (no README/gitignore, you already have
those), then:

```bash
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

Both teammates should now clone this and run steps in section 1 on their
own machines tonight.

## 3. Deploy to Render

**Easiest path — Blueprint deploy (uses `render.yaml` already in this repo):**

1. Go to https://dashboard.render.com → New → Blueprint
2. Connect your GitHub account and pick this repo
3. Render reads `render.yaml` and provisions both the web service and a free
   Postgres database automatically, wiring `DATABASE_URL` for you
4. Click Apply — first deploy takes a few minutes

**If Blueprint isn't available on your plan, do it manually instead:**

1. New → PostgreSQL → create a free instance, copy the **Internal Database
   URL**
2. New → Web Service → connect this repo
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
3. In the web service's Environment tab, add:
   - `DATABASE_URL` = the Postgres URL from step 1, but change `postgres://`
     at the very start to `postgresql://` (SQLAlchemy requires this exact
     prefix)
   - `SECRET_KEY` = output of the `secrets.token_hex(32)` command above
4. Deploy. Once live, visit `https://<your-service>.onrender.com/api/health`
   to confirm it's actually working in production, not just locally.

## 4. Confirm the pipeline end-to-end (do this tonight, not tomorrow)

- [ ] `/api/health` returns 200 locally
- [ ] `/api/health` returns 200 on the live Render URL
- [ ] Register + login works locally (check `/docs`)
- [ ] Register + login works on the live Render URL
- [ ] Both teammates have cloned, installed, and run this locally without errors
- [ ] `.env` is NOT committed to git (`git status` should not show it)

If all of these pass tonight, tomorrow you're only ever pushing feature
commits to something already known to work.

## Adding your idea's features tomorrow

- New DB tables → add a model in `app/models/`, import it in `app/main.py`
  near the other model imports (so `create_all` picks it up) or import it in
  `app/db/database.py`'s metadata scope
- New endpoints → new file in `app/routers/`, then
  `app.include_router(...)` in `app/main.py`
- Need a field validated → define it in `app/schemas/`
