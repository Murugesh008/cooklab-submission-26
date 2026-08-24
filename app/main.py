from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
import logging

from app.db.database import Base, engine

# Import all models so they're created in the database
from app.models.user import User
from app.workflows.models import Workflow, AuditLog
from app.order.models import Order
from app.services.crm.models import CRMRecord
from app.services.notification.models import Notification

# Import routers
from app.routers import auth, health, admin
from app.order.routers import router as order_router
from app.services.crm.routers import router as crm_router
from app.services.notification.routers import router as notification_router

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Hackathon-speed schema setup: create tables directly from models on
# startup. No Alembic migrations - fine because there's no real prod data
# to preserve across schema changes during a 16-hour build.
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Hackathon API - Workflow Orchestration")

# Wide open CORS for hackathon speed. Fine for a demo; tighten if you
# actually ship this somewhere real later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Makes sure a bug returns JSON, not FastAPI/Starlette's default HTML
    # error page - matters if a judge opens dev tools mid-demo.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Include existing routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(admin.router)

# Include workflow and service routers
app.include_router(order_router)
app.include_router(crm_router)
app.include_router(notification_router)

# Mount static files for frontend
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root():
    return {
        "message": "Workflow Orchestration API",
        "endpoints": {
            "docs": "/docs",
            "dashboard": "/static/index.html",
            "health": "/api/health",
            "order": "/api/order/create",
        }
    }
