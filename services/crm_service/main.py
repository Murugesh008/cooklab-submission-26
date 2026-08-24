from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, HTTPException, Depends, Query, status as http_status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from typing import Dict, Any, List, Optional
import logging
from sqlalchemy import create_engine, Column, Integer, String, JSON, DateTime, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session
import os
from dotenv import load_dotenv

PACKAGE_DIR = Path(__file__).parent
load_dotenv(PACKAGE_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("crm-service")

# Database setup
DATABASE_URL = os.getenv("CRM_DATABASE_URL", f"sqlite:///{PACKAGE_DIR / 'crm.db'}")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String, nullable=True)
    source = Column(String, default="directory", nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class CustomerEvent(Base):
    __tablename__ = "customer_events"
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String, index=True)
    event_type = Column(String)
    data = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class CRMUser(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

Base.metadata.create_all(bind=engine)

if "source" not in {column["name"] for column in inspect(engine).get_columns("customers")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE customers ADD COLUMN source VARCHAR DEFAULT 'directory' NOT NULL"))

with engine.begin() as connection:
    connection.execute(text("""
        UPDATE customers
        SET source = 'workflow_event'
        WHERE source = 'directory'
          AND name = substr(email, 1, instr(email, '@') - 1)
          AND EXISTS (
              SELECT 1 FROM customer_events
              WHERE customer_events.customer_id = customers.email
                AND customer_events.event_type = 'ORDER_PLACED'
          )
    """))

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

CRM_SECRET_KEY = os.getenv("CRM_SECRET_KEY")
if not CRM_SECRET_KEY:
    raise RuntimeError("CRM_SECRET_KEY must be configured for the CRM service")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("CRM_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
ALGORITHM = "HS256"
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

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

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True

def create_access_token(email: str) -> str:
    from datetime import timedelta, timezone
    expires = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({"sub": email, "exp": expires}, CRM_SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_error = HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, CRM_SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise credentials_error
    user = db.query(CRMUser).filter(CRMUser.email == email).first()
    if user is None:
        raise credentials_error
    return user

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

@app.post("/api/auth/register", response_model=UserOut, status_code=http_status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    if len(payload.password) < 6:
        raise HTTPException(status_code=422, detail="Password must be at least 6 characters")
    if db.query(CRMUser).filter(CRMUser.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = CRMUser(email=payload.email, hashed_password=password_context.hash(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/api/auth/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(CRMUser).filter(CRMUser.email == payload.email).first()
    if not user or not password_context.verify(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return Token(access_token=create_access_token(user.email))

@app.get("/api/auth/me", response_model=UserOut)
def read_current_user(current_user: CRMUser = Depends(get_current_user)):
    return current_user

@app.post("/customers")
def create_customer(cust: CustomerCreate, db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.email == cust.email).first()
    if db_cust:
        if db_cust.source == "workflow_event":
            db_cust.source = "directory"
            db_cust.name = cust.name
            db.commit()
            db.refresh(db_cust)
            return customer_payload(db_cust)
        raise HTTPException(status_code=409, detail="A customer with this email already exists")
    db_cust = Customer(email=cust.email, name=cust.name, source="directory")
    db.add(db_cust)
    db.commit()
    db.refresh(db_cust)
    return customer_payload(db_cust)

@app.get("/customers")
def list_customers(search: Optional[str] = Query(default=None), db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    query = db.query(Customer).filter(Customer.source == "directory")
    if search:
        term = f"%{search}%"
        query = query.filter((Customer.name.ilike(term)) | (Customer.email.ilike(term)))
    return [customer_payload(customer) for customer in query.order_by(Customer.created_at.desc()).all()]

@app.put("/customers/{customer_id}")
def update_customer(customer_id: int, cust: CustomerUpdate, db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.id == customer_id, Customer.source == "directory").first()
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
def delete_customer(customer_id: int, db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.id == customer_id, Customer.source == "directory").first()
    if not db_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.query(CustomerEvent).filter(CustomerEvent.customer_id == db_cust.email).delete()
    db.delete(db_cust)
    db.commit()

@app.get("/customers/{customer_id}")
def get_customer(customer_id: str, db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    db_cust = db.query(Customer).filter(Customer.id == int(customer_id), Customer.source == "directory").first()
    if not db_cust:
        raise HTTPException(status_code=404, detail="Customer not found")
    return customer_payload(db_cust)

@app.get("/customers/{customer_id}/events")
def list_events(customer_id: int, db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    customer = db.query(Customer).filter(Customer.id == customer_id, Customer.source == "directory").first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    events = db.query(CustomerEvent).filter(CustomerEvent.customer_id == customer.email).order_by(CustomerEvent.created_at.desc()).all()
    return [{"id": event.id, "customer_id": event.customer_id, "event_type": event.event_type, "data": event.data, "created_at": event.created_at} for event in events]

@app.get("/events")
def list_all_events(db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
    ensure_available()
    events = db.query(CustomerEvent).order_by(CustomerEvent.created_at.desc()).all()
    return [{"id": event.id, "customer_id": event.customer_id, "event_type": event.event_type, "data": event.data, "created_at": event.created_at} for event in events]

@app.post("/customers/{customer_id}/events")
def create_event(customer_id: str, event: EventCreate, db: Session = Depends(get_db), _: CRMUser = Depends(get_current_user)):
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
        db_cust = Customer(email=customer_email, name=customer_email.split("@")[0], source="workflow_event")
        db.add(db_cust)
        db.commit()
    
    event_data = {
        "workflow_id": req.workflow_id,
        "attempt": req.attempt
    }
    for field in ("sku", "quantity"):
        if req.payload.get(field) is not None:
            event_data[field] = req.payload[field]
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
