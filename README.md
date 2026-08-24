# Cooklab Workflow Platform and CRM Service

This repository contains the original workflow platform and a separately runnable CRM application. The workflow platform owns authentication, orders, workflow state, and orchestration. The CRM application owns customer profiles, customer events, its frontend, and its CRM database.

## What's Already Wired Up (Original)

- `POST /api/auth/register` — create a user
- `POST /api/auth/login` — get a JWT access token
- `GET /api/auth/me` — example protected route (needs `Authorization: Bearer <token>`)
- `GET /api/health` — health check
- `GET /docs` — interactive API docs (Swagger UI), auto-generated
- SQLAlchemy models + SQLite locally, swaps to Postgres on Render via `DATABASE_URL`
- Tables auto-create on startup (no Alembic — intentional, see `main.py` comment)
- Global JSON error handler so a crash returns JSON, not an HTML error page

## Repository Layout

```text
app/
   main.py                 Main API: auth, orders, workflow dashboard, legacy CRM workflow boundary
   db/                     Main application database setup
   models/                 Main application models, including users
   workflows/              Orchestrator, retries, idempotency, and audit logs
   static/                 Original workflow dashboard and a legacy CRM frontend copy

services/crm_service/
   main.py                 Standalone CRM FastAPI application
   static/crm/             Canonical CRM frontend served by the CRM application
   crm.db                  Standalone CRM SQLite database, created at runtime
   README.md               CRM-specific run instructions

services/inventory_service/
   main.py                 Standalone Inventory FastAPI application
   static/                 Inventory frontend served by the service

services/notification_service/
   main.py                 Standalone Notification FastAPI application
   static/                 Notification frontend served by the service
   notification.db         Notification database, created at runtime
   README.md               Notification-specific run instructions
```

## Workflow Platform

A complete **structural foundation** for Order → Inventory → CRM → Notification workflow orchestration:

- **Orchestrator engine** — executes multi-step workflows, handles retries, logs events
- **Independent services** — Inventory, CRM, Notification each with own API & database boundary
- **Order entry point** — REST API to create orders and trigger workflows
- **Audit logging** — complete immutable history of all workflow events
- **Step abstraction** — pipeline-oriented workflow definition (not yet fully generic)
- **Retry & idempotency boundaries** — structural support for future fault-tolerance features
- **Transformation layer** — isolates service input/output mapping
- **Vanilla frontend dashboard** — real-time workflow status visualization & execution logs

The workflow platform executes Order -> Inventory -> CRM -> Notification workflows. The orchestrator communicates with downstream services over HTTP and does not access their databases directly.

See [WORKFLOW_STRUCTURE.md](WORKFLOW_STRUCTURE.md) for detailed architecture and design decisions.

## Standalone Inventory Application

The inventory service is an independently runnable application at `services/inventory_service`. It owns its FastAPI backend, browser UI, inventory model, and SQLite database. It has no imports from the CRM or notification services and makes no outbound HTTP calls to them.

Start it from the repository root:

```bash
uvicorn services.inventory_service.main:app --host 0.0.0.0 --port 8001
```

Open the inventory UI at:

```text
http://localhost:8001/
```

The service also exposes its UI at `http://localhost:8001/static/index.html` and its API documentation at `http://localhost:8001/docs`.

### Inventory API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Inventory service health and failure-simulation status |
| `GET` | `/inventory` | List inventory items |
| `POST` | `/inventory` | Add an item (`product_id`, `name`, `quantity`, `status`) |
| `GET` | `/inventory/{product_id}` | Read one item |
| `POST` | `/inventory/reserve` | Reserve stock for an SKU and quantity |
| `POST` | `/inventory/release` | Release reserved stock |
| `POST` | `/api/inventory/process` | Workflow callback used by the orchestrator |

The local database is `inventory.db`, created from the process working directory. The service seeds `ITEM-001`, `ITEM-002`, and `DEFAULT-SKU` on startup. Failure demonstration controls are available at `/admin/simulate-failure`, `/admin/recover`, and `/admin/status`.

### Is Inventory Truly Independent?

**Yes, operationally and at the data boundary:**

- It runs as its own FastAPI process on port `8001`.
- It has its own SQLAlchemy `InventoryItem` model and SQLite database.
- It serves its own frontend and does not depend on the main app to render its UI.
- It does not call CRM, notification, or orchestrator services.
- The orchestrator calls it through the HTTP contract `/api/inventory/process`; this is an inbound workflow integration, not a direct database dependency.
- Docker Compose builds it from `services/inventory_service/Dockerfile` as a separate container.

**Current limitations:**

- Inventory API routes do not currently require authentication.
- `inventory.db` uses a relative SQLite URL, so its physical location depends on the process working directory. Container deployments still isolate the database in the inventory container, but a configurable absolute database URL would make the boundary more explicit.

The inventory service can therefore be stopped, restarted, or deployed separately from the main app. Workflow execution will observe the service outage and apply the orchestrator's retry/recovery policy.

## Standalone Notification Application

The notification service is a truly independent, separately runnable application at `services/notification_service`. It owns its FastAPI backend, browser frontend, notification model, and SQLite database. The service does not import the main application, access the main application's database, or make outbound calls to inventory, CRM, or the orchestrator.

Start it from the repository root:

```bash
uvicorn services.notification_service.main:app --host 0.0.0.0 --port 8003
```

Open the notification UI at:

```text
http://localhost:8003/
```

The service also exposes its UI at `http://localhost:8003/static/index.html` and its API documentation at `http://localhost:8003/docs`.

### Notification API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Notification service health and failure-simulation status |
| `GET` | `/notifications` | List the 50 most recent notifications |
| `POST` | `/notifications` | Send a notification (`type`, `recipient`, `subject`, `message`) |
| `GET` | `/notifications/{notification_id}` | Read one notification |
| `POST` | `/api/notification/process` | Workflow callback used by the orchestrator |

### Is Notification Truly Independent?

**Yes, operationally and at the data boundary:**

- It runs as its own FastAPI process on port `8003`.
- It owns its own `NotificationLog` model and SQLite database.
- It serves its own frontend from `/static` and does not depend on the main app to render its UI.
- Its frontend calls only the notification service's own origin.
- The orchestrator communicates with it only through the HTTP contract `/api/notification/process`; it does not access the notification database directly.
- Docker Compose runs it as a separate `notification-service` container and routes workflow calls to `http://notification-service:8003`.

The notification service can therefore be stopped, restarted, or deployed separately from the main app. Workflow execution will observe the outage and apply the orchestrator's retry/recovery policy.

**Current limitation:** notification delivery is simulated and persisted as `SENT` or `DELIVERED`; the service does not yet connect to an external email, SMS, or push provider. This limitation does not change its service independence, but it means the current system demonstrates delivery workflow and persistence rather than real-world message transmission.

## Standalone CRM Application

The canonical CRM application is `services/crm_service`. Its FastAPI backend, frontend, and customer database run as one separately deployable process on port `8002`.

Start the authentication provider and CRM application in separate terminals from the repository root:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000                         # authentication provider
uvicorn services.crm_service.main:app --reload --port 8002        # CRM application
```

Open the CRM at:

```text
http://localhost:8002/static/crm/
```

The CRM UI calls its own origin for customer and activity APIs. It calls the main application only for login, registration, and `/api/auth/me`. If authentication is hosted elsewhere, set `authApiUrl` in browser local storage to that server's `/api` URL.

### CRM API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | CRM service health and failure-simulation status |
| `GET` | `/customers?search=...` | List and search customers by name or email |
| `POST` | `/customers` | Create a customer (`email`, optional `name`) |
| `GET` | `/customers/{id}` | Read one customer |
| `PUT` | `/customers/{id}` | Update a customer |
| `DELETE` | `/customers/{id}` | Delete a customer and its events |
| `GET` | `/customers/{id}/events` | Read a customer's activity timeline |
| `POST` | `/customers/{id}/events` | Add an activity (`event_type`, `data`) |
| `GET` | `/events` | List all CRM events for dashboard statistics |
| `POST` | `/api/crm/process` | Workflow callback used by the orchestrator |

The CRM database defaults to `services/crm_service/crm.db`. Set `CRM_DATABASE_URL` to use another SQLite or SQLAlchemy-supported database URL.

### Is CRM Truly Independent?

**Yes, as a deployable service boundary:**

- It has its own FastAPI process and port (`8002`).
- It owns its own SQLAlchemy models, tables, and database file.
- It serves its own frontend at `/static/crm/`.
- It does not call inventory, notification, or orchestrator services.
- The orchestrator calls CRM through `/api/crm/process`, which is the intended downstream-service relationship.
- CRM can be stopped while the main workflow platform remains running.

**No, not fully autonomous today:**

- CRM login, registration, and token validation are provided by the main `app` at port `8000`.
- CRM customer routes currently accept the forwarded JWT but do not independently validate it.
- Docker Compose starts CRM as a separate container, but the CRM image is built from the repository root and shares the repository's Python requirements.

Therefore, CRM is independently deployable and database-isolated, but authentication is still a shared platform dependency. To make it fully autonomous, move or duplicate the auth/token verification contract into `services/crm_service`, or place authentication behind a shared identity service that CRM can validate independently.

### Failure Demonstration

The CRM service includes demo controls:

```bash
curl -X POST http://localhost:8002/admin/simulate-failure
curl http://localhost:8002/health
curl -X POST http://localhost:8002/admin/recover
```

When CRM is unavailable, the CRM frontend shows an explicit `CRM service unavailable` state with a Retry action. The original workflow dashboard remains at `http://localhost:8000/static/index.html`.

### Docker Compose

Run the complete multi-service system with:

```bash
docker compose up --build
```

The CRM container is exposed at `http://localhost:8002/static/crm/`, and the orchestrator uses `CRM_SERVICE_URL=http://crm-service:8002` for workflow callbacks.

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
