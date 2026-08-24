"""
CRM service business logic.

This service owns CRM operations and persistence.
It never directly accesses other services' databases.
It communicates with the orchestrator only through its API.
"""
import logging
from sqlalchemy.orm import Session
from app.services.crm.models import CRMRecord

logger = logging.getLogger(__name__)


class CRMService:
    """Service for CRM operations."""

    def __init__(self, db: Session):
        self.db = db

    def process_crm_request(
        self, workflow_id: int, customer_email: str, idempotency_key: str = None
    ) -> dict:
        """
        Process a CRM operation for a workflow.
        
        Returns a dict with the operation result.
        This will be called by the orchestrator through the API endpoint.
        """
        logger.info(
            f"[CRM] Processing workflow {workflow_id}: "
            f"customer_email={customer_email}"
        )

        # Check for idempotent replay
        if idempotency_key:
            existing = self.db.query(CRMRecord).filter(
                CRMRecord.idempotency_key == idempotency_key
            ).first()
            if existing:
                logger.info(
                    f"[CRM] Idempotent request detected "
                    f"(key={idempotency_key}), returning cached result"
                )
                return {
                    "customer_email": existing.customer_email,
                    "status": existing.status,
                }

        # Create CRM record
        record = CRMRecord(
            workflow_id=workflow_id,
            customer_email=customer_email,
            status="active",
            idempotency_key=idempotency_key,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        logger.info(
            f"[CRM] Request completed for workflow {workflow_id}: "
            f"customer={record.customer_email}, status={record.status}"
        )

        return {
            "customer_email": record.customer_email,
            "status": record.status,
        }

    def get_workflow_crm(self, workflow_id: int) -> dict:
        """Retrieve CRM state for a workflow."""
        record = self.db.query(CRMRecord).filter(
            CRMRecord.workflow_id == workflow_id
        ).first()
        if not record:
            return {"workflow_id": workflow_id, "record": None}
        return {
            "workflow_id": workflow_id,
            "record": {
                "customer_email": record.customer_email,
                "status": record.status,
            },
        }
