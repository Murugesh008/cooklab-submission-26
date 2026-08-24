"""
Inventory service business logic.

This service owns inventory operations and persistence.
It never directly accesses other services' databases.
It communicates with the orchestrator only through its API.
"""
import logging
from sqlalchemy.orm import Session
from app.services.inventory.models import InventoryItem

logger = logging.getLogger(__name__)


class InventoryService:
    """Service for inventory operations."""

    def __init__(self, db: Session):
        self.db = db

    def process_inventory_request(
        self, workflow_id: int, sku: str, quantity: int, idempotency_key: str = None
    ) -> dict:
        """
        Process an inventory operation for a workflow.
        
        Returns a dict with the operation result.
        This will be called by the orchestrator through the API endpoint.
        """
        logger.info(
            f"[INVENTORY] Processing workflow {workflow_id}: "
            f"SKU={sku}, qty={quantity}"
        )

        # Check for idempotent replay
        if idempotency_key:
            existing = self.db.query(InventoryItem).filter(
                InventoryItem.idempotency_key == idempotency_key
            ).first()
            if existing:
                logger.info(
                    f"[INVENTORY] Idempotent request detected "
                    f"(key={idempotency_key}), returning cached result"
                )
                return {
                    "sku": existing.sku,
                    "quantity_reserved": existing.quantity_reserved,
                    "quantity_available": existing.quantity_available,
                }

        # Create inventory record
        item = InventoryItem(
            workflow_id=workflow_id,
            sku=sku,
            quantity_reserved=quantity,
            quantity_available=100 - quantity,  # Simulated available inventory
            idempotency_key=idempotency_key,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)

        logger.info(
            f"[INVENTORY] Request completed for workflow {workflow_id}: "
            f"reserved={item.quantity_reserved}, available={item.quantity_available}"
        )

        return {
            "sku": item.sku,
            "quantity_reserved": item.quantity_reserved,
            "quantity_available": item.quantity_available,
        }

    def get_workflow_inventory(self, workflow_id: int) -> dict:
        """Retrieve inventory state for a workflow."""
        items = self.db.query(InventoryItem).filter(
            InventoryItem.workflow_id == workflow_id
        ).all()
        return {
            "workflow_id": workflow_id,
            "items": [
                {
                    "sku": item.sku,
                    "quantity_reserved": item.quantity_reserved,
                    "quantity_available": item.quantity_available,
                }
                for item in items
            ],
        }
