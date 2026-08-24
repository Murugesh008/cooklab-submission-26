from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, String, JSON, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory-service")

# Database setup
DATABASE_URL = "sqlite:///./inventory.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class InventoryItem(Base):
    __tablename__ = "inventory"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(String, unique=True, index=True)
    name = Column(String)
    available = Column(Integer, default=0)
    reserved = Column(Integer, default=0)
    status = Column(String, default="ACTIVE")

class ProcessedOperation(Base):
    __tablename__ = "processed_operations"
    id = Column(Integer, primary_key=True, index=True)
    operation_id = Column(String, unique=True, index=True, nullable=False)
    response = Column(JSON, nullable=False)

Base.metadata.create_all(bind=engine)

if "status" not in {column["name"] for column in inspect(engine).get_columns("inventory")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE inventory ADD COLUMN status VARCHAR DEFAULT 'ACTIVE'"))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Seed default items if they don't exist
def seed_db():
    db = SessionLocal()
    default_items = [
        {"product_id": "ITEM-001", "name": "Laptop", "available": 50, "reserved": 5, "status": "ACTIVE"},
        {"product_id": "ITEM-002", "name": "Headphones", "available": 100, "reserved": 10, "status": "ACTIVE"},
        {"product_id": "DEFAULT-SKU", "name": "Generic Item", "available": 200, "reserved": 0, "status": "ACTIVE"},
    ]
    for item_data in default_items:
        if not db.query(InventoryItem).filter(InventoryItem.product_id == item_data["product_id"]).first():
            item = InventoryItem(**item_data)
            db.add(item)
    db.commit()
    db.close()

seed_db()

app = FastAPI(title="Inventory Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Failure simulation state
failure_simulation = {"is_failed": False, "failure_code": 500, "failure_message": "Inventory Service simulated failure"}

class ReserveRequest(BaseModel):
    sku: str
    quantity: int

class InventoryItemCreate(BaseModel):
    product_id: str
    name: str
    quantity: int
    status: str = "ACTIVE"

class InventoryItemUpdate(BaseModel):
    name: str
    quantity: int
    status: str = "ACTIVE"

class ProcessRequest(BaseModel):
    workflow_id: int
    step_name: str
    attempt: int
    payload: Dict[str, Any]

@app.get("/health")
def health():
    return {
        "status": "healthy" if not failure_simulation["is_failed"] else "unhealthy",
        "service": "inventory_service",
        "simulated_failure": failure_simulation["is_failed"]
    }

@app.get("/inventory")
def list_inventory(db: Session = Depends(get_db)):
    return [
        {"product_id": item.product_id, "name": item.name, "available": item.available,
         "reserved": item.reserved, "status": item.status or "ACTIVE"}
        for item in db.query(InventoryItem).order_by(InventoryItem.product_id).all()
    ]

@app.post("/inventory", status_code=201)
def add_inventory_item(req: InventoryItemCreate, db: Session = Depends(get_db)):
    product_id = req.product_id.strip()
    name = req.name.strip()
    if not product_id or not name:
        raise HTTPException(status_code=400, detail="Product ID and name are required")
    if req.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity cannot be negative")
    if req.status not in {"ACTIVE", "LOW_STOCK", "OUT_OF_STOCK", "DISCONTINUED"}:
        raise HTTPException(status_code=400, detail="Invalid inventory status")
    if db.query(InventoryItem).filter(InventoryItem.product_id == product_id).first():
        raise HTTPException(status_code=409, detail="Product ID already exists")
    item = InventoryItem(product_id=product_id, name=name, available=req.quantity,
                         reserved=0, status=req.status)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"product_id": item.product_id, "name": item.name, "available": item.available,
            "reserved": item.reserved, "status": item.status}

@app.get("/inventory/{product_id}")
def get_inventory(product_id: str, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    item = db.query(InventoryItem).filter(InventoryItem.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product_id": item.product_id, "name": item.name, "available": item.available, "reserved": item.reserved, "status": item.status or "ACTIVE"}

@app.put("/inventory/{product_id}")
def update_inventory_item(product_id: str, req: InventoryItemUpdate, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Item name is required")
    if req.quantity < item.reserved:
        raise HTTPException(status_code=400, detail="Quantity cannot be less than reserved stock")
    if req.status not in {"ACTIVE", "LOW_STOCK", "OUT_OF_STOCK", "DISCONTINUED"}:
        raise HTTPException(status_code=400, detail="Invalid inventory status")
    item.name = name
    item.available = req.quantity - item.reserved
    item.status = req.status
    db.commit()
    db.refresh(item)
    return {"product_id": item.product_id, "name": item.name, "available": item.available,
            "reserved": item.reserved, "status": item.status}

@app.delete("/inventory/{product_id}", status_code=204)
def delete_inventory_item(product_id: str, db: Session = Depends(get_db)):
    item = db.query(InventoryItem).filter(InventoryItem.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    db.delete(item)
    db.commit()

@app.post("/inventory/reserve")
def reserve_inventory(req: ReserveRequest, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    
    item = db.query(InventoryItem).filter(InventoryItem.product_id == req.sku).first()
    if not item:
        item = db.query(InventoryItem).filter(InventoryItem.product_id == "DEFAULT-SKU").first()
        
    if item.available < req.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")
    
    item.available -= req.quantity
    item.reserved += req.quantity
    item.status = "OUT_OF_STOCK" if item.available == 0 else "LOW_STOCK" if item.available <= 10 else "ACTIVE"
    db.commit()
    return {"status": "reserved", "sku": req.sku, "quantity": req.quantity, "remaining": item.available}

@app.post("/inventory/release")
def release_inventory(req: ReserveRequest, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    item = db.query(InventoryItem).filter(InventoryItem.product_id == req.sku).first()
    if not item:
        item = db.query(InventoryItem).filter(InventoryItem.product_id == "DEFAULT-SKU").first()
        
    item.available += req.quantity
    item.reserved = max(0, item.reserved - req.quantity)
    item.status = "ACTIVE"
    db.commit()
    return {"status": "released", "sku": req.sku, "quantity": req.quantity}

@app.post("/api/inventory/process")
def process_step(req: ProcessRequest, db: Session = Depends(get_db)):
    operation_id = req.payload.get("operation_id", f"{req.workflow_id}:{req.step_name}")
    cached = db.query(ProcessedOperation).filter(ProcessedOperation.operation_id == operation_id).first()
    if cached:
        return cached.response

    if failure_simulation["is_failed"]:
        logger.warning(f"[INVENTORY] Rejecting request due to simulated failure for workflow {req.workflow_id}")
        return {
            "success": False,
            "message": f"Inventory Service Error: {failure_simulation['failure_message']}",
            "data": None
        }
    
    sku = req.payload.get("sku", "ITEM-001")
    quantity = req.payload.get("quantity", 1)
    
    item = db.query(InventoryItem).filter(InventoryItem.product_id == sku).first()
    if not item:
        item = db.query(InventoryItem).filter(InventoryItem.product_id == "DEFAULT-SKU").first()
        
    if item.available < quantity:
        return {"success": False, "message": f"Insufficient stock for SKU {sku}", "data": None}
    
    item.available -= quantity
    item.reserved += quantity
    item.status = "OUT_OF_STOCK" if item.available == 0 else "LOW_STOCK" if item.available <= 10 else "ACTIVE"
    db.commit()
    
    logger.info(f"[INVENTORY] Reserved {quantity} of {sku} for workflow {req.workflow_id}")
    
    result = {
        "success": True,
        "message": f"Successfully reserved {quantity} of {sku}",
        "data": {
            "sku": sku,
            "quantity": quantity,
            "status": "RESERVED",
            "inventory_id": f"INV-{req.workflow_id}"
        }
    }
    db.add(ProcessedOperation(operation_id=operation_id, response=result))
    db.commit()
    return result

@app.post("/admin/simulate-failure")
def simulate_failure(code: int = 500, message: str = "Simulated Inventory Service Outage"):
    failure_simulation["is_failed"] = True
    failure_simulation["failure_code"] = code
    failure_simulation["failure_message"] = message
    logger.warning("[INVENTORY] Failure simulation ENABLED")
    return {"status": "failure_simulated", "service": "inventory_service", "is_failed": True}

@app.post("/admin/recover")
def recover():
    failure_simulation["is_failed"] = False
    logger.info("[INVENTORY] Service RECOVERED")
    return {"status": "recovered", "service": "inventory_service", "is_failed": False}

@app.get("/admin/status")
def status():
    return {
        "service": "inventory_service",
        "is_failed": failure_simulation["is_failed"],
        "failure_message": failure_simulation["failure_message"]
    }

@app.get("/", include_in_schema=False)
def inventory_home():
    return RedirectResponse(url="/static/index.html")

app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static", html=True), name="inventory-static")
