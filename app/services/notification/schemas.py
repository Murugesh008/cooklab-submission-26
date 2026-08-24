from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


class NotificationCreate(BaseModel):
    recipient_email: EmailStr
    subject: str
    message: str


class NotificationOut(BaseModel):
    id: int
    workflow_id: int
    recipient_email: EmailStr
    subject: str
    message: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
