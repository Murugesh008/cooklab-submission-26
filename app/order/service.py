"""
Order service business logic.

Handles order creation and workflow orchestration initiation.
"""
import logging
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.order.models import Order
from app.workflows.orchestrator import WorkflowOrchestrator
from app.workflows.step import RetryPolicy, StepDefinition

logger = logging.getLogger(__name__)


class OrderService:
    """Service for order operations and workflow orchestration."""

    def __init__(self, db: Session):
        self.db = db

    def create_order_and_execute_workflow(
        self, customer_email: str, sku: str, quantity: int
    ) -> dict:
        """
        Create an order and execute the complete workflow.
        
        Returns order and workflow information.
        """
        # Generate unique order ID
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        logger.info(
            f"[ORDER] Creating order {order_id} for {customer_email}: "
            f"SKU={sku}, qty={quantity}"
        )

        # Create order record
        payload = {
            "customer_email": customer_email,
            "sku": sku,
            "quantity": quantity,
            "recipient_email": customer_email,
            "subject": f"Order {order_id} Confirmation",
            "message": f"Your order for {quantity}x {sku} has been placed",
        }

        order = Order(
            order_id=order_id,
            customer_email=customer_email,
            sku=sku,
            quantity=quantity,
            payload=payload,
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)

        logger.info(f"[ORDER] Order {order_id} created (db_id={order.id})")

        # Create and execute workflow
        orchestrator = WorkflowOrchestrator(self.db)
        workflow = orchestrator.create_workflow(external_id=order_id, payload=payload)
        logger.info(
            f"[ORDER] Workflow created (workflow_id={workflow.id}) "
            f"for order {order_id}"
        )

        import os

        # Define the workflow pipeline
        inventory_url = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8001") + "/api/inventory/process"
        crm_url = os.getenv("CRM_SERVICE_URL", "http://localhost:8002") + "/api/crm/process"
        notification_url = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8003") + "/api/notification/process"

        steps = [
            StepDefinition(
                name="inventory",
                service_endpoint=inventory_url,
                retry_policy=RetryPolicy(max_attempts=2),
                transform_request=lambda p: {
                    "sku": p.get("sku"),
                    "quantity": p.get("quantity"),
                },
                transform_response=lambda r: r,
            ),
            StepDefinition(
                name="crm",
                service_endpoint=crm_url,
                retry_policy=RetryPolicy(max_attempts=2),
                transform_request=lambda p: {
                    "customer_email": p.get("customer_email"),
                    "sku": p.get("sku"),
                    "quantity": p.get("quantity"),
                },
                transform_response=lambda r: r,
            ),
            StepDefinition(
                name="notification",
                service_endpoint=notification_url,
                retry_policy=RetryPolicy(max_attempts=2),
                transform_request=lambda p: {
                    "recipient_email": p.get("customer_email"),
                    "subject": p.get("subject"),
                    "message": p.get("message"),
                },
                transform_response=lambda r: r,
            ),
        ]

        # Execute workflow
        workflow = orchestrator.execute_workflow(workflow, steps)
        logger.info(
            f"[ORDER] Workflow execution completed "
            f"(workflow_id={workflow.id}, status={workflow.status})"
        )

        # Update order with workflow reference
        order.workflow_id = workflow.id
        order.workflow_status = workflow.status.value
        order.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "order_id": order.order_id,
            "workflow_id": workflow.id,
            "status": workflow.status.value,
            "message": "Order processed and workflow executed",
        }

    def get_order(self, order_id: str) -> dict:
        """Retrieve order details."""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if not order:
            return None

        return {
            "order_id": order.order_id,
            "customer_email": order.customer_email,
            "sku": order.sku,
            "quantity": order.quantity,
            "workflow_id": order.workflow_id,
            "workflow_status": order.workflow_status,
        }

    def get_order_history(self, order_id: str) -> dict:
        """Retrieve order and its complete workflow history."""
        order = self.db.query(Order).filter(Order.order_id == order_id).first()
        if not order or not order.workflow_id:
            return None

        orchestrator = WorkflowOrchestrator(self.db)
        history = orchestrator.get_workflow_history(order.workflow_id)

        return {
            "order_id": order.order_id,
            "workflow_id": order.workflow_id,
            "status": order.workflow_status,
            "events": [
                {
                    "timestamp": event.timestamp.isoformat(),
                    "event_type": event.event_type.value,
                    "step": event.step,
                    "attempt": event.attempt,
                    "error_message": event.error_message,
                }
                for event in history
            ],
        }


from datetime import datetime
