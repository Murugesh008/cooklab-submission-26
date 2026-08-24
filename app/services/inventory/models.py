from sqlalchemy import Column, Integer, JSON, String, DateTime
from datetime import datetime

from app.db.database import Base


class InventoryItem(Base):
    """
    Represents inventory state for workflow items.
    
    Each service owns its own database and models.
    The orchestrator communicates only through this service's API.
    """
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=False, index=True)
    sku = Column(String, nullable=False)
    quantity_reserved = Column(Integer, default=0)
    quantity_available = Column(Integer, default=0)
    # For idempotency - detect replayed requests
    idempotency_key = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
