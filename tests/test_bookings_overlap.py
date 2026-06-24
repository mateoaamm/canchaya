"""Capa 1 anti-solapamiento (chequeo en codigo) + reglas de horario y TZ."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.enums import UserRole
from app.models.availability import AvailabilityRule
from app.models.court import Court
from app.models.venue import Venue

TZ = ZoneInfo("America/Bogota")


def _seed(db):
    venue = Venue(name="Sede", address="Cra 1", timezone="America/Bogota")
    db.add(venue)
    db.flush()
    court = Court(venue_id=venue.id, name="C1")
    db.add(court)
    db.flush()
    for wd in range(7):
        db.add(
            AvailabilityRule(court_id=court.id, weekday=wd, open_time=time(8), close_time=time(22))
        )
    db.commit()
    db.refresh(court)
    return court


def _book(client, token, court_id, start, end, auth):
    return client.post(
        "/bookings",
        json={"court_id": court_id, "start_time": start.isoformat(), "end_time": end.isoformat()},
        headers=auth(token),
    )


def _slot(hour):
    base = (datetime.now(TZ) + timedelta(days=2)).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return base, base + timedelta(hours=1)


def test_overlapping_booking_is_rejected(client, db, make_user, login, auth):
    court = _seed(db)
    make_user(email="u1@example.com", role=UserRole.CLIENT)
    make_user(email="u2@example.com", role=UserRole.CLIENT)
    t1, t2 = login("u1@example.com"), login("u2@example.com")

    s, e = _slot(10)
    assert _book(client, t1, court.id, s, e, auth).status_code == 201
    # Mismo horario, otro usuario -> 409
    assert _book(client, t2, court.id, s, e, auth).status_code == 409
    # Solape parcial -> 409
    assert (
        _book(
            client, t2, court.id, s + timedelta(minutes=30), e + timedelta(minutes=30), auth
        ).status_code
        == 409
    )


def test_adjacent_bookings_are_allowed(client, db, make_user, login, auth):
    """Una reserva que empieza justo cuando termina otra NO es solape."""
    court = _seed(db)
    make_user(email="u@example.com", role=UserRole.CLIENT)
    t = login("u@example.com")
    s, e = _slot(14)
    assert _book(client, t, court.id, s, e, auth).status_code == 201
    assert _book(client, t, court.id, e, e + timedelta(hours=1), auth).status_code == 201


def test_booking_outside_hours_is_rejected(client, db, make_user, login, auth):
    court = _seed(db)
    make_user(email="u@example.com", role=UserRole.CLIENT)
    t = login("u@example.com")
    # 06:00, antes de abrir (08:00) -> 422
    base = (datetime.now(TZ) + timedelta(days=2)).replace(hour=6, minute=0, second=0, microsecond=0)
    assert _book(client, t, court.id, base, base + timedelta(hours=1), auth).status_code == 422


def test_cancelled_slot_can_be_rebooked(client, db, make_user, login, auth):
    court = _seed(db)
    make_user(email="u@example.com", role=UserRole.CLIENT)
    t = login("u@example.com")
    s, e = _slot(16)
    r = _book(client, t, court.id, s, e, auth)
    bid = r.json()["id"]
    # Cancelar libera el horario (el constraint excluye las canceladas)
    assert client.post(f"/bookings/{bid}/cancel", headers=auth(t)).status_code == 200
    assert _book(client, t, court.id, s, e, auth).status_code == 201
