from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class OrderCreate(BaseModel):
    customer_email: EmailStr
    sku: str
    quantity: int = 1


class OrderOut(BaseModel):
    id: int
    order_id: str
    customer_email: EmailStr
    sku: str
    quantity: int
    workflow_id: Optional[int] = None
    workflow_status: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    order_id: str
    workflow_id: int
    status: str
    message: str
