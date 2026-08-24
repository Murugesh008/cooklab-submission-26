from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

from app.db.database import Base


class CRMRecord(Base):
    """
    Represents CRM state for workflow participants.
    
    Each service owns its own database and models.
    The orchestrator communicates only through this service's API.
    """
    __tablename__ = "crm_records"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=False, index=True)
    customer_email = Column(String, nullable=False)
    status = Column(String, default="active")
    # For idempotency - detect replayed requests
    idempotency_key = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
