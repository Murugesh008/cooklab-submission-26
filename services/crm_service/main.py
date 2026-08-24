from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crm-service")

# Database setup
DATABASE_URL = os.getenv("CRM_DATABASE_URL", f"sqlite:///{Path(__file__).parent / 'crm.db'}")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class CustomerEvent(Base):
    __tablename__ = "customer_events"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    event_type = Column(String)
    data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

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

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="crm-static")

# Failure simulation state
failure_simulation = {"is_failed": False, "failure_code": 500, "failure_message": "CRM Service simulated failure"}

class CustomerCreate(BaseModel):
    email: str
    name: Optional[str] = None

class CustomerUpdate(BaseModel):
    email: Optional[str] = None
    name: Optional[str] = None

class EventCreate(BaseModel):
    customer_id: str
    event_type: str
    data: Dict[str, Any]

def ensure_available():
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])

def customer_payload(customer):
    return {
        "id": customer.id,
        "email": customer.email,
        "name": customer.name,
        "created_at": customer.created_at,
        "updated_at": customer.updated_at,
    }

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
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.email == cust.email).first()
    if db_cust:
        raise HTTPException(status_code=409, detail="A customer with this email already exists")
    db_cust = Customer(email=cust.email, name=cust.name)
    db.add(db_cust)
    db.commit()
    db.refresh(db_cust)
    return customer_payload(db_cust)

@app.get("/customers")
def list_customers(search: Optional[str] = Query(default=None), db: Session = Depends(get_db)):
    ensure_available()
    query = db.query(Customer)
    if search:
        term = f"%{search}%"
        query = query.filter((Customer.name.ilike(term)) | (Customer.email.ilike(term)))
    return [customer_payload(customer) for customer in query.order_by(Customer.created_at.desc()).all()]

@app.put("/customers/{customer_id}")
def update_customer(customer_id: int, cust: CustomerUpdate, db: Session = Depends(get_db)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    if cust.email is not None and cust.email != db_cust.email:
        duplicate = db.query(Customer).filter(Customer.email == cust.email).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="A customer with this email already exists")
        db_cust.email = cust.email
    if cust.name is not None:
        db_cust.name = cust.name
    db.commit()
    db.refresh(db_cust)
    return customer_payload(db_cust)

@app.delete("/customers/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.id == customer_id).first()
    if not db_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.query(CustomerEvent).filter(CustomerEvent.customer_id == db_cust.email).delete()
    db.delete(db_cust)
    db.commit()

@app.get("/customers/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_db)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.id == int(customer_id)).first()
    if not db_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer_payload(db_cust)

@app.get("/customers/{customer_id}/events")
def list_events(customer_id: int, db: Session = Depends(get_db)):
    ensure_available()
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    events = db.query(CustomerEvent).filter(CustomerEvent.customer_id == customer.email).order_by(CustomerEvent.created_at.desc()).all()
    return [{"id": event.id, "customer_id": event.customer_id, "event_type": event.event_type, "data": event.data, "created_at": event.created_at} for event in events]

@app.get("/events")
def list_all_events(db: Session = Depends(get_db)):
    ensure_available()
    events = db.query(CustomerEvent).order_by(CustomerEvent.created_at.desc()).all()
    return [{"id": event.id, "customer_id": event.customer_id, "event_type": event.event_type, "data": event.data, "created_at": event.created_at} for event in events]

@app.post("/customers/{customer_id}/events")
def create_event(customer_id: str, event: EventCreate, db: Session = Depends(get_db)):
    ensure_available()
    customer = db.query(Customer).filter(Customer.id == int(customer_id)).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    event_record = CustomerEvent(customer_id=customer.email, event_type=event.event_type, data=event.data)
    db.add(event_record)
    db.commit()
    db.refresh(event_record)
    return {"id": event_record.id, "customer_id": customer.id, "event_type": event_record.event_type, "data": event_record.data, "created_at": event_record.created_at}

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
