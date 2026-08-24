from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging
from sqlalchemy import create_engine, Column, Integer, String
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

Base.metadata.create_all(bind=engine)

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
        {"product_id": "ITEM-001", "name": "Laptop", "available": 50, "reserved": 5},
        {"product_id": "ITEM-002", "name": "Headphones", "available": 100, "reserved": 10},
        {"product_id": "DEFAULT-SKU", "name": "Generic Item", "available": 200, "reserved": 0},
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

@app.get("/inventory/{product_id}")
def get_inventory(product_id: str, db: Session = Depends(get_db)):
    if failure_simulation["is_failed"]:
        raise HTTPException(status_code=failure_simulation["failure_code"], detail=failure_simulation["failure_message"])
    item = db.query(InventoryItem).filter(InventoryItem.product_id == product_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"product_id": item.product_id, "name": item.name, "available": item.available, "reserved": item.reserved}

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
    db.commit()
    return {"status": "released", "sku": req.sku, "quantity": req.quantity}

@app.post("/api/inventory/process")
def process_step(req: ProcessRequest, db: Session = Depends(get_db)):
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
    db.commit()
    
    logger.info(f"[INVENTORY] Reserved {quantity} of {sku} for workflow {req.workflow_id}")
    
    return {
        "success": True,
        "message": f"Successfully reserved {quantity} of {sku}",
        "data": {
            "sku": sku,
            "quantity": quantity,
            "status": "RESERVED",
            "inventory_id": f"INV-{req.workflow_id}"
        }
    }

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
