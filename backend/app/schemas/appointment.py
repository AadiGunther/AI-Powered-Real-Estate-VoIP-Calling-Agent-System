from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class AppointmentResponse(BaseModel):
    id: int
    call_id: int
    lead_id: int
    scheduled_for: datetime
    address: str
    contact_number: Optional[str] = None
    notes: Optional[str] = None
    status: str

    client_name: Optional[str] = None
    service_type: str = "site_visit"
    duration_minutes: int = 60
    assigned_staff_id: Optional[int] = None
    assigned_staff_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AppointmentListResponse(BaseModel):
    appointments: List[AppointmentResponse]
    total: int
    page: int
    page_size: int


class AppointmentUpdate(BaseModel):
    scheduled_for: Optional[datetime] = None
    address: Optional[str] = Field(None, min_length=2, max_length=255)
    contact_number: Optional[str] = Field(None, min_length=5, max_length=50)
    notes: Optional[str] = None
    status: Optional[str] = None
    assigned_staff_id: Optional[int] = None


class AppointmentRescheduleRequest(BaseModel):
    scheduled_for: datetime
