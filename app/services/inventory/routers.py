"""
Inventory service API routes.

This is the boundary between the orchestrator and inventory domain logic.
The orchestrator calls this API; it never accesses the DB directly.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.workflows.step import StepRequest, StepResponse
from app.services.inventory.service import InventoryService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/inventory", tags=["inventory"])


@router.post("/process", response_model=StepResponse)
def process_inventory_step(request: StepRequest, db: Session = Depends(get_db)):
    """
    Process inventory step of a workflow.
    
    Expected payload structure:
    {
        "sku": "ITEM-001",
        "quantity": 5
    }
    """
    try:
        logger.info(
            f"[INVENTORY] Received workflow step request: "
            f"workflow_id={request.workflow_id}, step={request.step_name}, "
            f"attempt={request.attempt}"
        )

        service = InventoryService(db)
        payload = request.payload

        sku = payload.get("sku", "DEFAULT-SKU")
        quantity = payload.get("quantity", 1)
        idempotency_key = f"{request.workflow_id}#{request.step_name}#{request.attempt}"

        result = service.process_inventory_request(
            workflow_id=request.workflow_id,
            sku=sku,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )

        return StepResponse(
            success=True, message="Inventory processed successfully", data=result
        )
    except Exception as e:
        logger.error(f"[INVENTORY] Error processing workflow: {str(e)}")
        return StepResponse(
            success=False, message=f"Inventory processing failed: {str(e)}"
        )


@router.get("/workflow/{workflow_id}")
def get_workflow_inventory(workflow_id: int, db: Session = Depends(get_db)):
    """Retrieve inventory state for a workflow."""
    service = InventoryService(db)
    return service.get_workflow_inventory(workflow_id)
