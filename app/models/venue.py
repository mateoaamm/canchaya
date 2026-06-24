from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.court import Court
    from app.models.user import User


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # Zona horaria IANA (ej. "America/Bogota"). Guardamos todo en UTC en la BD,
    # pero la sede define en que TZ se interpretan los horarios de atencion.
    timezone: Mapped[str] = mapped_column(String(64), default="America/Bogota", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    courts: Mapped[list["Court"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )
    staff: Mapped[list["User"]] = relationship(back_populates="venue")
