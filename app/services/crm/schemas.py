from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class CRMRecordCreate(BaseModel):
    customer_email: EmailStr
    status: str = "active"


class CRMRecordOut(BaseModel):
    id: int
    workflow_id: int
    customer_email: EmailStr
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
