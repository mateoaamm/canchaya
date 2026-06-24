"""TEST ESTRELLA: el EXCLUDE constraint de Postgres gana la carrera.

Aqui NO pasamos por la capa de codigo (que tiene su propio 'if'). Insertamos
dos reservas SOLAPADAS desde dos conexiones/hilos a la vez, directo a la BD.
Esto simula el caso real: dos requests que llegan en el mismo instante, ambos
chequean y ven el horario libre, ambos intentan insertar.

Resultado esperado: EXACTAMENTE una se inserta. La otra es rechazada por la BD
con una ExclusionViolation. Es la garantia que un 'if' en Python no puede dar.

Mecanica: con un EXCLUDE gist, el INSERT del segundo hilo se BLOQUEA esperando
a que el primero confirme; cuando el primero hace commit, el segundo falla.
Por eso necesitamos hilos reales (no dos sesiones en un solo hilo, que se
auto-bloquearia).
"""

import threading
from datetime import UTC, datetime, time, timedelta

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.enums import BookingStatus
from app.models.availability import AvailabilityRule
from app.models.booking import Booking
from app.models.court import Court
from app.models.user import User


@pytest.fixture
def scenario(db):
    """Crea sede, cancha, regla horaria y un usuario. Devuelve (court_id, user_id)."""
    from app.models.venue import Venue

    venue = Venue(name="Sede", address="Cra 1", timezone="America/Bogota")
    db.add(venue)
    db.flush()
    court = Court(venue_id=venue.id, name="C1")
    db.add(court)
    db.flush()
    for wd in range(7):
        db.add(
            AvailabilityRule(
                court_id=court.id, weekday=wd, open_time=time(0), close_time=time(23, 59)
            )
        )
    user = User(email="race@example.com", hashed_password="x", full_name="Race")
    db.add(user)
    db.commit()
    return court.id, user.id


def test_concurrent_overlapping_inserts_only_one_wins(scenario):
    court_id, user_id = scenario
    start = datetime(2030, 1, 1, 18, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)

    barrier = threading.Barrier(2)
    results: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        session = SessionLocal()
        try:
            booking = Booking(
                court_id=court_id,
                user_id=user_id,
                start_time=start,
                end_time=end,
                status=BookingStatus.PENDING,
            )
            session.add(booking)
            barrier.wait(timeout=5)  # arrancan a la vez
            session.commit()
            with lock:
                results.append("ok")
        except IntegrityError:
            session.rollback()
            with lock:
                results.append("conflict")
        finally:
            session.close()

    t1 = threading.Thread(target=worker)
    t2 = threading.Thread(target=worker)
    t1.start()
    t2.start()
    t1.join(timeout=15)
    t2.join(timeout=15)

    # Exactamente una gana, exactamente una choca. La BD lo garantiza.
    assert sorted(results) == ["conflict", "ok"], results

    # Y en la base quedo una sola reserva activa.
    check = SessionLocal()
    try:
        count = (
            check.query(Booking)
            .filter(Booking.court_id == court_id, Booking.status != BookingStatus.CANCELLED)
            .count()
        )
    finally:
        check.close()
    assert count == 1


def test_exclusion_violation_is_the_underlying_error(scenario):
    """Confirma que el error subyacente es ExclusionViolation de Postgres."""
    court_id, user_id = scenario
    start = datetime(2030, 2, 1, 12, 0, tzinfo=UTC)
    end = start + timedelta(hours=2)

    s1 = SessionLocal()
    s1.add(
        Booking(
            court_id=court_id,
            user_id=user_id,
            start_time=start,
            end_time=end,
            status=BookingStatus.PENDING,
        )
    )
    s1.commit()
    s1.close()

    s2 = SessionLocal()
    s2.add(
        Booking(
            court_id=court_id,
            user_id=user_id,
            start_time=start + timedelta(minutes=30),
            end_time=end + timedelta(minutes=30),
            status=BookingStatus.PENDING,
        )
    )
    with pytest.raises(IntegrityError) as exc_info:
        s2.commit()
    s2.rollback()
    s2.close()
    assert isinstance(exc_info.value.orig, psycopg.errors.ExclusionViolation)
