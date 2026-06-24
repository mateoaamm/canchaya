from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.enums import BookingStatus

if TYPE_CHECKING:
    from app.models.court import Court
    from app.models.payment import Payment
    from app.models.user import User


class Booking(Base):
    """Reserva de una cancha en un rango de tiempo.

    start_time/end_time son timestamptz: SIEMPRE en UTC en la base.
    La proteccion contra doble reserva tiene DOS capas:
      1) Chequeo en codigo (booking_service) -> da un 409 amable.
      2) EXCLUDE constraint en Postgres (migracion 0002) -> garantia real
         bajo concurrencia, imposible de saltarse aunque dos requests
         lleguen en el mismo milisegundo.
    """

    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    court_id: Mapped[int] = mapped_column(ForeignKey("courts.id"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status", values_callable=lambda e: [m.value for m in e]),
        default=BookingStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    court: Mapped["Court"] = relationship(back_populates="bookings")
    user: Mapped["User"] = relationship(back_populates="bookings")
    payment: Mapped["Payment | None"] = relationship(
        back_populates="booking", uselist=False, cascade="all, delete-orphan"
    )
