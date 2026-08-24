"""
CRM service API routes.

This is the boundary between the orchestrator and CRM domain logic.
The orchestrator calls this API; it never accesses the DB directly.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.workflows.step import StepRequest, StepResponse
from app.services.crm.service import CRMService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/crm", tags=["crm"])


@router.post("/process", response_model=StepResponse)
def process_crm_step(request: StepRequest, db: Session = Depends(get_db)):
    """
    Process CRM step of a workflow.
    
    Expected payload structure:
    {
        "customer_email": "customer@example.com"
    }
    """
    try:
        logger.info(
            f"[CRM] Received workflow step request: "
            f"workflow_id={request.workflow_id}, step={request.step_name}, "
            f"attempt={request.attempt}"
        )

        service = CRMService(db)
        payload = request.payload

        customer_email = payload.get("customer_email", "unknown@example.com")
        idempotency_key = f"{request.workflow_id}#{request.step_name}#{request.attempt}"

        result = service.process_crm_request(
            workflow_id=request.workflow_id,
            customer_email=customer_email,
            idempotency_key=idempotency_key,
        )

        return StepResponse(
            success=True, message="CRM processed successfully", data=result
        )
    except Exception as e:
        logger.error(f"[CRM] Error processing workflow: {str(e)}")
        return StepResponse(success=False, message=f"CRM processing failed: {str(e)}")


@router.get("/workflow/{workflow_id}")
def get_workflow_crm(workflow_id: int, db: Session = Depends(get_db)):
    """Retrieve CRM state for a workflow."""
    service = CRMService(db)
    return service.get_workflow_crm(workflow_id)
