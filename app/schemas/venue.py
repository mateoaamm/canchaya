from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VenueCreate(BaseModel):
    name: str
    address: str
    timezone: str = "America/Bogota"


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    address: str
    timezone: str
    created_at: datetime
