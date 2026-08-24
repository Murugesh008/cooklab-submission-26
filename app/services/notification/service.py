"""
Notification service business logic.

This service owns notification operations and persistence.
It never directly accesses other services' databases.
It communicates with the orchestrator only through its API.
"""
import logging
from sqlalchemy.orm import Session
from app.services.notification.models import Notification, NotificationStatus

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for notification operations."""

    def __init__(self, db: Session):
        self.db = db

    def process_notification_request(
        self,
        workflow_id: int,
        recipient_email: str,
        subject: str = "Workflow Update",
        message: str = "",
        idempotency_key: str = None,
    ) -> dict:
        """
        Process a notification operation for a workflow.
        
        Returns a dict with the operation result.
        This will be called by the orchestrator through the API endpoint.
        """
        logger.info(
            f"[NOTIFICATION] Processing workflow {workflow_id}: "
            f"recipient={recipient_email}, subject={subject}"
        )

        # Check for idempotent replay
        if idempotency_key:
            existing = self.db.query(Notification).filter(
                Notification.idempotency_key == idempotency_key
            ).first()
            if existing:
                logger.info(
                    f"[NOTIFICATION] Idempotent request detected "
                    f"(key={idempotency_key}), returning cached result"
                )
                return {
                    "recipient_email": existing.recipient_email,
                    "subject": existing.subject,
                    "status": existing.status.value,
                }

        # Create notification record
        notification = Notification(
            workflow_id=workflow_id,
            recipient_email=recipient_email,
            subject=subject,
            message=message,
            status=NotificationStatus.SENT,  # Simulated success
            idempotency_key=idempotency_key,
        )
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)

        logger.info(
            f"[NOTIFICATION] Request completed for workflow {workflow_id}: "
            f"recipient={notification.recipient_email}, status={notification.status}"
        )

        return {
            "recipient_email": notification.recipient_email,
            "subject": notification.subject,
            "status": notification.status.value,
        }

    def get_workflow_notifications(self, workflow_id: int) -> dict:
        """Retrieve notification state for a workflow."""
        notifications = self.db.query(Notification).filter(
            Notification.workflow_id == workflow_id
        ).all()
        return {
            "workflow_id": workflow_id,
            "notifications": [
                {
                    "recipient_email": n.recipient_email,
                    "subject": n.subject,
                    "status": n.status.value,
                }
                for n in notifications
            ],
        }
