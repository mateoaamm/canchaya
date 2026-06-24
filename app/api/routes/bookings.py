"""Reservas: crear, listar (con scope por rol), cancelar, confirmar pago.

Aqui vive la doble capa anti-solapamiento y la autorizacion por ownership.
"""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from psycopg.errors import ExclusionViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.enums import BookingStatus, PaymentStatus, UserRole
from app.models.booking import Booking
from app.models.court import Court
from app.models.payment import Payment
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut
from app.services.booking_service import (
    BookingError,
    overlaps_in_code,
    validate_within_hours,
)

router = APIRouter(tags=["bookings"])

_PRICE_PER_BOOKING = Decimal("80000.00")  # COP, simulado


def _can_manage_booking(user: User, booking: Booking, court: Court) -> bool:
    """Admin: todo. Staff: solo su sede. Cliente: solo lo suyo."""
    if user.role == UserRole.ADMIN:
        return True
    if user.role == UserRole.STAFF:
        return user.venue_id == court.venue_id
    return booking.user_id == user.id


@router.post("/bookings", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    data: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    court = db.get(Court, data.court_id)
    if court is None or not court.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cancha no disponible")

    # 1) Reglas de negocio (horario de atencion, no cruzar medianoche, etc.)
    try:
        validate_within_hours(db, court, data.start_time, data.end_time)
    except BookingError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    # 2) Capa 1 anti-solapamiento: chequeo en codigo (UX amable)
    if overlaps_in_code(db, court.id, data.start_time, data.end_time):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya esta reservado")

    booking = Booking(
        court_id=court.id,
        user_id=current_user.id,
        start_time=data.start_time,
        end_time=data.end_time,
        status=BookingStatus.PENDING,
    )
    booking.payment = Payment(amount=_PRICE_PER_BOOKING, status=PaymentStatus.PENDING)
    db.add(booking)

    # 3) Capa 2 (backstop real): si la carrera se perdio, la BD lo impide.
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        if isinstance(exc.orig, ExclusionViolation):
            raise HTTPException(status.HTTP_409_CONFLICT, "Ese horario ya esta reservado") from exc
        raise
    db.refresh(booking)
    return booking


@router.get("/bookings", response_model=list[BookingOut])
def list_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Booking]:
    """Cliente: sus reservas. Staff: las de su sede. Admin: todas."""
    stmt = select(Booking).order_by(Booking.start_time.desc())
    if current_user.role == UserRole.CLIENT:
        stmt = stmt.where(Booking.user_id == current_user.id)
    elif current_user.role == UserRole.STAFF:
        stmt = stmt.join(Court).where(Court.venue_id == current_user.venue_id)
    return list(db.scalars(stmt))


@router.get("/bookings/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada")
    court = db.get(Court, booking.court_id)
    if court is None or not _can_manage_booking(current_user, booking, court):
        # 404 (no 403) para no revelar que la reserva existe a quien no le concierne.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada")
    return booking


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Booking:
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada")
    court = db.get(Court, booking.court_id)
    if court is None or not _can_manage_booking(current_user, booking, court):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada")
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "La reserva ya estaba cancelada")

    booking.status = BookingStatus.CANCELLED
    if booking.payment and booking.payment.status == PaymentStatus.PAID:
        booking.payment.status = PaymentStatus.REFUNDED
    db.commit()
    db.refresh(booking)
    return booking


@router.post("/bookings/{booking_id}/confirm-payment", response_model=BookingOut)
def confirm_payment(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN)),
) -> Booking:
    """El staff confirma el pago -> la reserva pasa a CONFIRMED."""
    booking = db.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Reserva no encontrada")
    court = db.get(Court, booking.court_id)
    if court is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cancha no encontrada")
    if current_user.role == UserRole.STAFF and current_user.venue_id != court.venue_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No es tu sede")
    if booking.status == BookingStatus.CANCELLED:
        raise HTTPException(status.HTTP_409_CONFLICT, "No se puede confirmar una cancelada")

    if booking.payment:
        booking.payment.status = PaymentStatus.PAID
    booking.status = BookingStatus.CONFIRMED
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/courts/{court_id}/bookings", response_model=list[BookingOut])
def court_bookings(
    court_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.STAFF, UserRole.ADMIN)),
) -> list[Booking]:
    """Vista de staff/admin: todas las reservas de una cancha."""
    court = db.get(Court, court_id)
    if court is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cancha no encontrada")
    if current_user.role == UserRole.STAFF and current_user.venue_id != court.venue_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No es tu sede")
    return list(
        db.scalars(select(Booking).where(Booking.court_id == court_id).order_by(Booking.start_time))
    )
