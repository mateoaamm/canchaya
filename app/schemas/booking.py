from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.enums import BookingStatus, PaymentStatus


class BookingCreate(BaseModel):
    court_id: int
    start_time: datetime  # ISO 8601; se recomienda enviar con offset (ej. ...-05:00)
    end_time: datetime

    @model_validator(mode="after")
    def _check_range(self) -> "BookingCreate":
        if self.end_time <= self.start_time:
            raise ValueError("end_time debe ser posterior a start_time")
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    amount: float
    method: str
    status: PaymentStatus


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    court_id: int
    user_id: int
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    created_at: datetime
    payment: PaymentOut | None = None
