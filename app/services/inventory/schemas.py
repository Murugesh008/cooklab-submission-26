from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class InventoryItemCreate(BaseModel):
    sku: str
    quantity_reserved: int = 0
    quantity_available: int = 0


class InventoryItemOut(BaseModel):
    id: int
    workflow_id: int
    sku: str
    quantity_reserved: int
    quantity_available: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
