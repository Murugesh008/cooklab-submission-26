"""
Workflow Orchestrator Entry Point.

Runs the main Orchestrator FastAPI application on port 8000.
Coordinates the three downstream services:
- Inventory Service (Port 8001)
- CRM Service (Port 8002)
- Notification Service (Port 8003)
"""
from app.main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("orchestrator.main:app", host="0.0.0.0", port=8000, reload=True)
