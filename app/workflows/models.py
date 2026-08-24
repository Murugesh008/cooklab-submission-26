from datetime import datetime
from enum import Enum

from sqlalchemy import JSON, Column, DateTime, Enum as SQLEnum, Integer, String

from app.db.database import Base


class WorkflowStatus(str, Enum):
    """Workflow execution status."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    WAITING_RETRY = "WAITING_RETRY"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class AuditEventType(str, Enum):
    """Event types for audit log."""
    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    STEP_STARTED = "STEP_STARTED"
    STEP_SUCCEEDED = "STEP_SUCCEEDED"
    STEP_FAILED = "STEP_FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    RETRY_FAILED = "RETRY_FAILED"
    RETRY_SUCCEEDED = "RETRY_SUCCEEDED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"


class Workflow(Base):
    """
    Represents the mutable state of a workflow execution.
    
    This is distinct from audit history - it tracks only current state:
    status, current step, attempt count. Historical events are in AuditLog.
    """
    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    # Unique workflow identifier (e.g., order_id)
    external_id = Column(String, unique=True, index=True, nullable=False)
    status = Column(SQLEnum(WorkflowStatus), default=WorkflowStatus.PENDING, nullable=False)
    current_step = Column(String, nullable=True)  # e.g., "inventory", "crm", "notification"
    attempt_count = Column(Integer, default=0)
    # Payload of the workflow (the order data, etc.)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class AuditLog(Base):
    """
    Append-oriented audit log. Every workflow event is recorded here immutably.
    
    This is the authoritative history of what happened, separate from mutable workflow state.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, nullable=False, index=True)  # Foreign key to Workflow
    step = Column(String, nullable=True)  # Step name (e.g., "inventory", "crm")
    event_type = Column(SQLEnum(AuditEventType), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    attempt = Column(Integer, default=0)
    error_message = Column(String, nullable=True)
    # Arbitrary event data for extensibility
    event_data = Column(JSON, nullable=True)
