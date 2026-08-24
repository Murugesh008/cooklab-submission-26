# Standalone CRM Application

This package owns the CRM FastAPI backend, frontend, authentication, and database. It does not call inventory, notification, or orchestrator services.

From the repository root:

```bash
uvicorn services.crm_service.main:app --host 0.0.0.0 --port 8002
```

Open `http://localhost:8002/static/crm/`. Register and log in using the CRM's own `/api/auth` endpoints.

The CRM owns its users table and JWT signing key. Set `CRM_SECRET_KEY` in every deployment. To use a different database, set `CRM_DATABASE_URL`.

For local development, create `services/crm_service/.env` with:

```env
CRM_SECRET_KEY=replace-with-a-long-random-secret
CRM_ACCESS_TOKEN_EXPIRE_MINUTES=1440
```

The service loads this file automatically. It is ignored by Git and must be created separately in each deployment environment.