from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import Surface

if TYPE_CHECKING:
    from app.models.availability import AvailabilityRule
    from app.models.booking import Booking
    from app.models.venue import Venue


class Court(Base):
    __tablename__ = "courts"

    id: Mapped[int] = mapped_column(primary_key=True)
    venue_id: Mapped[int] = mapped_column(ForeignKey("venues.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    surface: Mapped[Surface] = mapped_column(
        Enum(Surface, name="surface", values_callable=lambda e: [m.value for m in e]),
        default=Surface.SYNTHETIC,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    venue: Mapped["Venue"] = relationship(back_populates="courts")
    availability_rules: Mapped[list["AvailabilityRule"]] = relationship(
        back_populates="court", cascade="all, delete-orphan"
    )
    bookings: Mapped[list["Booking"]] = relationship(back_populates="court")
