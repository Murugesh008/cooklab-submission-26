from sqlalchemy import Column, Integer, String, DateTime, Enum as SQLEnum
from datetime import datetime
from enum import Enum

from app.db.database import Base


class NotificationStatus(str, Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class Notification(Base):
    """
    Represents notification state for workflow events.
    
    Each service owns its own database and models.
    The orchestrator communicates only through this service's API.
    """
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=False, index=True)
    recipient_email = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    message = Column(String, nullable=False)
    status = Column(SQLEnum(NotificationStatus), default=NotificationStatus.PENDING)
    # For idempotency - detect replayed requests
    idempotency_key = Column(String, unique=True, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
