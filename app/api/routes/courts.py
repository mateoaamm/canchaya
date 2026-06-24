"""Disponibilidad de canchas: reglas de horario (admin) y slots libres (consulta)."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.enums import BookingStatus, UserRole
from app.models.availability import AvailabilityRule
from app.models.booking import Booking
from app.models.court import Court
from app.models.user import User
from app.schemas.court import (
    AvailabilityRuleCreate,
    AvailabilityRuleOut,
    CourtOut,
    FreeSlot,
)

router = APIRouter(prefix="/courts", tags=["courts"])


@router.get("", response_model=list[CourtOut])
def list_courts(
    venue_id: int | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Court]:
    stmt = select(Court).order_by(Court.id)
    if venue_id is not None:
        stmt = stmt.where(Court.venue_id == venue_id)
    return list(db.scalars(stmt))


@router.post(
    "/{court_id}/availability",
    response_model=AvailabilityRuleOut,
    status_code=status.HTTP_201_CREATED,
)
def add_availability_rule(
    court_id: int,
    data: AvailabilityRuleCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> AvailabilityRule:
    if db.get(Court, court_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cancha no encontrada")
    if data.close_time <= data.open_time:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "close_time <= open_time")
    rule = AvailabilityRule(court_id=court_id, **data.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.get("/{court_id}/availability", response_model=list[FreeSlot])
def get_availability(
    court_id: int,
    day: date = Query(..., description="Fecha a consultar (YYYY-MM-DD)"),
    slot_minutes: int = Query(60, ge=15, le=240),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[FreeSlot]:
    """Calcula los slots libres de una cancha en una fecha.

    Toma el horario de atencion del dia, lo parte en slots de `slot_minutes`,
    y descarta los que se solapen con reservas no canceladas. Todo se calcula
    en la zona horaria de la sede y se devuelve en ISO 8601 con offset.
    """
    court = db.get(Court, court_id)
    if court is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cancha no encontrada")

    tz = ZoneInfo(court.venue.timezone)
    rule = db.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.court_id == court_id,
            AvailabilityRule.weekday == day.weekday(),
        )
    )
    if rule is None:
        return []

    # Reservas activas de ese dia (rango local del dia convertido a UTC).
    day_start = datetime.combine(day, time.min, tzinfo=tz)
    day_end = day_start + timedelta(days=1)
    booked = list(
        db.scalars(
            select(Booking).where(
                Booking.court_id == court_id,
                Booking.status != BookingStatus.CANCELLED,
                Booking.start_time < day_end,
                day_start < Booking.end_time,
            )
        )
    )

    slots: list[FreeSlot] = []
    cursor = datetime.combine(day, rule.open_time, tzinfo=tz)
    window_end = datetime.combine(day, rule.close_time, tzinfo=tz)
    step = timedelta(minutes=slot_minutes)

    while cursor + step <= window_end:
        slot_end = cursor + step
        overlap = any(
            b.start_time.astimezone(tz) < slot_end and cursor < b.end_time.astimezone(tz)
            for b in booked
        )
        if not overlap:
            slots.append(FreeSlot(start=cursor.isoformat(), end=slot_end.isoformat()))
        cursor = slot_end

    return slots
