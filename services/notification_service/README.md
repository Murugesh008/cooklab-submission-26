# Standalone Notification Service

This package owns the notification FastAPI service, frontend, and SQLite database.

From the repository root:

```bash
uvicorn services.notification_service.main:app --host 0.0.0.0 --port 8003
```

Open `http://localhost:8003/`. The service also exposes the UI at `/static/index.html` and API documentation at `/docs`.

The browser UI calls only this service's origin. It can compose email, SMS, and push notifications, inspect the recent delivery log, and exercise the failure/recovery controls used by the workflow demo.