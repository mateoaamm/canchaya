from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.enums import UserRole


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    venue_id: int | None
    is_active: bool
    created_at: datetime


class StaffCreate(BaseModel):
    """Admin crea staff/admin y los asigna a una sede."""

    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.STAFF
    venue_id: int | None = None
