from sqlalchemy import Column, Integer, String, DateTime, JSON
from datetime import datetime

from app.db.database import Base


class Order(Base):
    """
    Represents an order that triggers a workflow.
    
    This is the entry point for the workflow orchestration.
    When an order is created, a workflow is initiated.
    """
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, unique=True, index=True, nullable=False)
    customer_email = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    # Workflow state reference
    workflow_id = Column(Integer, nullable=True, index=True)
    workflow_status = Column(String, nullable=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
