from datetime import time

from pydantic import BaseModel, ConfigDict, field_validator

from app.enums import Surface


class CourtCreate(BaseModel):
    venue_id: int
    name: str
    surface: Surface = Surface.SYNTHETIC


class CourtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    venue_id: int
    name: str
    surface: Surface
    is_active: bool


class AvailabilityRuleCreate(BaseModel):
    weekday: int  # 0=lunes .. 6=domingo
    open_time: time
    close_time: time

    @field_validator("weekday")
    @classmethod
    def _weekday_range(cls, v: int) -> int:
        if not 0 <= v <= 6:
            raise ValueError("weekday debe estar entre 0 (lunes) y 6 (domingo)")
        return v


class AvailabilityRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    court_id: int
    weekday: int
    open_time: time
    close_time: time


class FreeSlot(BaseModel):
    start: str  # ISO 8601 con offset
    end: str
