"""
Notification service API routes.

This is the boundary between the orchestrator and notification domain logic.
The orchestrator calls this API; it never accesses the DB directly.
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.workflows.step import StepRequest, StepResponse
from app.services.notification.service import NotificationService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/notification", tags=["notification"])


@router.post("/process", response_model=StepResponse)
def process_notification_step(request: StepRequest, db: Session = Depends(get_db)):
    """
    Process notification step of a workflow.
    
    Expected payload structure:
    {
        "recipient_email": "customer@example.com",
        "subject": "Order Confirmation",
        "message": "Your order has been placed"
    }
    """
    try:
        logger.info(
            f"[NOTIFICATION] Received workflow step request: "
            f"workflow_id={request.workflow_id}, step={request.step_name}, "
            f"attempt={request.attempt}"
        )

        service = NotificationService(db)
        payload = request.payload

        recipient_email = payload.get("recipient_email", "unknown@example.com")
        subject = payload.get("subject", "Workflow Update")
        message = payload.get("message", "Your workflow has been processed")
        idempotency_key = f"{request.workflow_id}#{request.step_name}#{request.attempt}"

        result = service.process_notification_request(
            workflow_id=request.workflow_id,
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            idempotency_key=idempotency_key,
        )

        return StepResponse(
            success=True, message="Notification processed successfully", data=result
        )
    except Exception as e:
        logger.error(f"[NOTIFICATION] Error processing workflow: {str(e)}")
        return StepResponse(
            success=False, message=f"Notification processing failed: {str(e)}"
        )


@router.get("/workflow/{workflow_id}")
def get_workflow_notifications(workflow_id: int, db: Session = Depends(get_db)):
    """Retrieve notification state for a workflow."""
    service = NotificationService(db)
    return service.get_workflow_notifications(workflow_id)
