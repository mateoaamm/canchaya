from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import UserRole

if TYPE_CHECKING:
    from app.models.booking import Booking
    from app.models.venue import Venue


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        default=UserRole.CLIENT,
        nullable=False,
    )
    # Solo el staff pertenece a una sede; clientes y admin lo tienen en NULL.
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    venue: Mapped["Venue | None"] = relationship(back_populates="staff")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")
