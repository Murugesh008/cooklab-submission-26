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

The CRM UI calls its own origin for authentication, customer, and activity APIs. CRM owns its users table and signs its own JWTs with `CRM_SECRET_KEY`; no login, registration, or token validation request goes to port `8000`.

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
- It owns registration, login, `/api/auth/me`, password hashing, and JWT validation.
- It does not call inventory, notification, orchestrator, or the main app.
- The orchestrator calls CRM through `/api/crm/process`, which is the intended downstream-service relationship.
- CRM can be stopped while the main workflow platform remains running.

**Deployment caveats:**

- Docker Compose builds the CRM image from the repository root and shares the repository's Python requirements, although the process and database remain separate.
- The orchestrator can call the intentionally separate `/api/crm/process` workflow callback; this is an inbound integration, not a CRM dependency on the orchestrator.

CRM is therefore independently deployable, database-isolated, and authentication-independent. The service requires a strong unique `CRM_SECRET_KEY` and can use a persistent `CRM_DATABASE_URL`; local development loads both settings from `services/crm_service/.env`, which is ignored by Git.
