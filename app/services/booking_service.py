"""Logica de negocio de reservas: validacion de horario y anti-solapamiento.

Defensa en profundidad:
  1) overlaps_in_code(): query que detecta choques -> 409 amable ANTES de insertar.
  2) El EXCLUDE constraint de Postgres es el backstop real: si dos requests
     ganan la carrera al mismo tiempo, la BD rechaza al perdedor con
     IntegrityError. La capa 1 mejora UX; la capa 2 garantiza correctitud.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.enums import BookingStatus
from app.models.availability import AvailabilityRule
from app.models.booking import Booking
from app.models.court import Court


class BookingError(Exception):
    """Error de negocio. La capa de API lo traduce a 409/422 segun el caso."""


def _to_utc(dt: datetime) -> datetime:
    """Normaliza a UTC. Si llega naive, se asume que ya esta en UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo("UTC"))


def validate_within_hours(db: Session, court: Court, start: datetime, end: datetime) -> None:
    """La reserva debe caer dentro del horario de atencion de ese dia.

    Los horarios se interpretan en la zona horaria de la sede.
    """
    venue_tz = ZoneInfo(court.venue.timezone)
    local_start = _to_utc(start).astimezone(venue_tz)
    local_end = _to_utc(end).astimezone(venue_tz)

    # No permitimos reservas que crucen la medianoche (simplificacion de alcance).
    if local_start.date() != local_end.date():
        raise BookingError("La reserva no puede cruzar la medianoche")

    weekday = local_start.weekday()  # 0=lunes
    rule = db.scalar(
        select(AvailabilityRule).where(
            AvailabilityRule.court_id == court.id,
            AvailabilityRule.weekday == weekday,
        )
    )
    if rule is None:
        raise BookingError("La cancha no atiende ese dia")

    if not (rule.open_time <= local_start.time() and local_end.time() <= rule.close_time):
        raise BookingError(f"Fuera del horario de atencion ({rule.open_time}-{rule.close_time})")


def overlaps_in_code(db: Session, court_id: int, start: datetime, end: datetime) -> bool:
    """True si ya existe una reserva NO cancelada que se solapa.

    Condicion clasica de solapamiento de intervalos [s,e):
        existing.start < new.end  AND  new.start < existing.end
    Nota: reservas adyacentes (una termina justo cuando empieza la otra)
    NO se consideran solape, gracias al uso de < (no <=).
    """
    start_u, end_u = _to_utc(start), _to_utc(end)
    stmt = select(Booking.id).where(
        Booking.court_id == court_id,
        Booking.status != BookingStatus.CANCELLED,
        Booking.start_time < end_u,
        start_u < Booking.end_time,
    )
    return db.scalar(stmt) is not None
