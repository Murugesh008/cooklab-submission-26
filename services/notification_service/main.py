from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
import uuid
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification-service")

# Database setup
DATABASE_URL = "sqlite:///./notification.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class NotificationLog(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    notification_id = Column(String, unique=True, index=True)
    type = Column(String)
    recipient = Column(String)
    subject = Column(String)
    message = Column(String)
    status = Column(String)
    workflow_id = Column(Integer, nullable=True)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="Notification Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Failure simulation state
failure_simulation = {"is_failed": False, "failure_code": 500, "failure_message": "Notification Service simulated failure"}

class NotificationCreate(BaseModel):
    type: str = "email" # email, sms, push
    recipient: str
    subject: Optional[str] = "Notification"
    message: str

class ProcessRequest(BaseModel):
    workflow_id: int
    step_name: str
    attempt: int
    payload: Dict[str, Any]

@app.get("/health")
def health():
    return {
        "status": "healthy" if not failure_simulation["is_failed"] else "unhealthy",
        "service": "notification_service",
        "simulated_failure": failure_simulation["is_failed"]
    }

@app.post("/notifications")
def send_notification(notif: NotificationCreate, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    
    notif_id = f"NOTIF-{uuid.uuid4().hex[:6].upper()}"
    record = NotificationLog(
        notification_id=notif_id,
        type=notif.type,
        recipient=notif.recipient,
        subject=notif.subject,
        message=notif.message,
        status="DELIVERED"
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    
    return {
        "notification_id": record.notification_id,
        "type": record.type,
        "recipient": record.recipient,
        "subject": record.subject,
        "message": record.message,
        "status": record.status
    }

@app.get("/notifications/{notification_id}")
def get_notification(notification_id: str, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    
    record = db.query(NotificationLog).filter(NotificationLog.notification_id == notification_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Notification not found")
        
    return {
        "notification_id": record.notification_id,
        "type": record.type,
        "recipient": record.recipient,
        "subject": record.subject,
        "message": record.message,
        "status": record.status
    }

@app.post("/api/notification/process")
def process_step(req: ProcessRequest, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        logger.warning(f"[NOTIFICATION] Rejecting request due to simulated failure for workflow {req.workflow_id}")
        return {
            "success": False,
            "message": f"Notification Service Error: {failure_simulation['failure_message']}",
            "data": None
        }
    
    recipient = req.payload.get("recipient_email", req.payload.get("customer_email", "customer@example.com"))
    subject = req.payload.get("subject", f"Order Update for Workflow #{req.workflow_id}")
    message = req.payload.get("message", "Your request has been processed successfully.")
    
    notif_id = f"NOTIF-{req.workflow_id}"
    record = NotificationLog(
        notification_id=notif_id,
        workflow_id=req.workflow_id,
        type="email",
        recipient=recipient,
        subject=subject,
        message=message,
        status="SENT"
    )
    db.add(record)
    db.commit()
    
    logger.info(f"[NOTIFICATION] Sent email to {recipient} for workflow {req.workflow_id}")
    
    return {
        "success": True,
        "message": f"Notification sent to {recipient}",
        "data": {
            "notification_id": notif_id,
            "recipient": recipient,
            "status": "SENT"
        }
    }

@app.post("/admin/simulate-failure")
def simulate_failure(code: int = 500, message: str = "Simulated Notification Service Outage"):
    failure_simulation["is_failed"] = True
    failure_simulation["failure_code"] = code
    failure_simulation["failure_message"] = message
    logger.warning("[NOTIFICATION] Failure simulation ENABLED")
    return {"status": "failure_simulated", "service": "notification_service", "is_failed": True}

@app.post("/admin/recover")
def recover():
    failure_simulation["is_failed"] = False
    logger.info("[NOTIFICATION] Service RECOVERED")
    return {"status": "recovered", "service": "notification_service", "is_failed": False}

@app.get("/admin/status")
def status():
    return {
        "service": "notification_service",
        "is_failed": failure_simulation["is_failed"],
        "failure_message": failure_simulation["failure_message"]
    }
