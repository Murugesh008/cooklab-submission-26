from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
from sqlalchemy import create_engine, Column, Integer, String, JSON, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crm-service")

# Database setup
DATABASE_URL = "sqlite:///./crm.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)

class CustomerEvent(Base):
    __tablename__ = "customer_events"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    event_type = Column(String)
    data = Column(JSON)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app = FastAPI(title="CRM Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Failure simulation state
failure_simulation = {"is_failed": False, "failure_code": 500, "failure_message": "CRM Service simulated failure"}

class CustomerCreate(BaseModel):
    email: str
    name: Optional[str] = None

class EventCreate(BaseModel):
    customer_id: str
    event_type: str
    data: Dict[str, Any]

class ProcessRequest(BaseModel):
    workflow_id: int
    step_name: str
    attempt: int
    payload: Dict[str, Any]

@app.get("/health")
def health():
    return {
        "status": "healthy" if not failure_simulation["is_failed"] else "unhealthy",
        "service": "crm_service",
        "simulated_failure": failure_simulation["is_failed"]
    }

@app.post("/customers")
def create_customer(cust: CustomerCreate, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    db_cust = db.query(Customer).filter(Customer.email == cust.email).first()
    if not db_cust:
        db_cust = Customer(email=cust.email, name=cust.name or cust.email.split("@")[0])
        db.add(db_cust)
        db.commit()
        db.refresh(db_cust)
    return {"email": db_cust.email, "name": db_cust.name}

@app.get("/customers/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    db_cust = db.query(Customer).filter(Customer.email == customer_id).first()
    if not db_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return {"email": db_cust.email, "name": db_cust.name}

@app.post("/customers/{customer_id}/events")
def create_event(customer_id: str, event: EventCreate, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    event_record = CustomerEvent(customer_id=customer_id, event_type=event.event_type, data=event.data)
    db.add(event_record)
    db.commit()
    db.refresh(event_record)
    return {"customer_id": event_record.customer_id, "type": event_record.event_type, "data": event_record.data}

@app.post("/api/crm/process")
def process_step(req: ProcessRequest, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        logger.warning(f"[CRM] Rejecting request due to simulated failure for workflow {req.workflow_id}")
        return {
            "success": False,
            "message": f"CRM Service Error: {failure_simulation['failure_message']}",
            "data": None
        }
    
    customer_email = req.payload.get("customer_email", "customer@example.com")
    
    # Store customer event in CRM database
    db_cust = db.query(Customer).filter(Customer.email == customer_email).first()
    if not db_cust:
        db_cust = Customer(email=customer_email, name=customer_email.split("@")[0])
        db.add(db_cust)
        db.commit()
    
    event_data = {
        "workflow_id": req.workflow_id,
        "attempt": req.attempt
    }
    event_record = CustomerEvent(customer_id=customer_email, event_type="ORDER_PLACED", data=event_data)
    db.add(event_record)
    db.commit()
    
    logger.info(f"[CRM] Logged customer event for {customer_email} in workflow {req.workflow_id}")
    
    return {
        "success": True,
        "message": f"CRM event logged successfully for {customer_email}",
        "data": {
            "customer_email": customer_email,
            "crm_id": f"CRM-{req.workflow_id}",
            "status": "RECORDED"
        }
    }

@app.post("/admin/simulate-failure")
def simulate_failure(code: int = 500, message: str = "Simulated CRM Service Outage"):
    failure_simulation["is_failed"] = True
    failure_simulation["failure_code"] = code
    failure_simulation["failure_message"] = message
    logger.warning("[CRM] Failure simulation ENABLED")
    return {"status": "failure_simulated", "service": "crm_service", "is_failed": True}

@app.post("/admin/recover")
def recover():
    failure_simulation["is_failed"] = False
    logger.info("[CRM] Service RECOVERED")
    return {"status": "recovered", "service": "crm_service", "is_failed": False}

@app.get("/admin/status")
def status():
    return {
        "service": "crm_service",
        "is_failed": failure_simulation["is_failed"],
        "failure_message": failure_simulation["failure_message"]
    }
