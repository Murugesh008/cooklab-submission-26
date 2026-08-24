# Standalone CRM Application

This package owns the CRM FastAPI backend, frontend, and SQLite database. It does not call inventory, notification, or orchestrator services.

From the repository root:

```bash
uvicorn services.crm_service.main:app --host 0.0.0.0 --port 8002
```

Open `http://localhost:8002/static/crm/`.

The UI uses the existing main application authentication API at `http://localhost:8000/api/auth`. To point authentication somewhere else, set `authApiUrl` in browser local storage. To use a different database, set `CRM_DATABASE_URL`.