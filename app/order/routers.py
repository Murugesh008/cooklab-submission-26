"""
Order service API routes.

Entry point for creating orders and triggering workflow execution.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.order.schemas import OrderCreate, OrderResponse, OrderOut
from app.order.service import OrderService
from app.workflows.models import Workflow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/order", tags=["order"])


@router.post("/create", response_model=OrderResponse)
def create_order(payload: OrderCreate, db: Session = Depends(get_db)):
    """
    Create an order and execute the workflow pipeline.
    
    This triggers:
    1. Inventory reservation
    2. CRM update
    3. Notification send
    """
    try:
        logger.info(f"[ORDER API] Received order creation request for {payload.customer_email}")
        service = OrderService(db)
        result = service.create_order_and_execute_workflow(
            customer_email=payload.customer_email,
            sku=payload.sku,
            quantity=payload.quantity,
        )
        return result
    except Exception as e:
        logger.error(f"[ORDER API] Error creating order: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Order creation failed: {str(e)}")


@router.get("/status/{order_id}")
def get_order_status(order_id: str, db: Session = Depends(get_db)):
    """Retrieve order and workflow status."""
    service = OrderService(db)
    order = service.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.get("/history/{order_id}")
def get_order_history(order_id: str, db: Session = Depends(get_db)):
    """Retrieve complete order execution history."""
    service = OrderService(db)
    history = service.get_order_history(order_id)
    if not history:
        raise HTTPException(status_code=404, detail="Order or workflow not found")
    return history
