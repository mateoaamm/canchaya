"""Tests del calculo de slots libres (endpoint GET /courts/{id}/availability)."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.enums import UserRole
from app.models.availability import AvailabilityRule
from app.models.court import Court
from app.models.venue import Venue

TZ = ZoneInfo("America/Bogota")


def _seed(db, open_h=8, close_h=12):
    venue = Venue(name="Sede", address="Cra 1", timezone="America/Bogota")
    db.add(venue)
    db.flush()
    court = Court(venue_id=venue.id, name="C1")
    db.add(court)
    db.flush()
    for wd in range(7):
        db.add(
            AvailabilityRule(
                court_id=court.id, weekday=wd, open_time=time(open_h), close_time=time(close_h)
            )
        )
    db.commit()
    db.refresh(court)
    return court


def test_availability_returns_hourly_slots(client, db, make_user, login, auth):
    court = _seed(db, 8, 12)  # 4 horas -> 4 slots de 60 min
    make_user(email="u@example.com", role=UserRole.CLIENT)
    token = login("u@example.com")
    day = (datetime.now(TZ) + timedelta(days=3)).date().isoformat()
    r = client.get(
        f"/courts/{court.id}/availability",
        params={"day": day, "slot_minutes": 60},
        headers=auth(token),
    )
    assert r.status_code == 200
    assert len(r.json()) == 4


def test_availability_excludes_booked_slot(client, db, make_user, login, auth):
    court = _seed(db, 8, 12)
    make_user(email="u@example.com", role=UserRole.CLIENT)
    token = login("u@example.com")
    target = (datetime.now(TZ) + timedelta(days=3)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    booked = client.post(
        "/bookings",
        json={
            "court_id": court.id,
            "start_time": target.isoformat(),
            "end_time": (target + timedelta(hours=1)).isoformat(),
        },
        headers=auth(token),
    )
    assert booked.status_code == 201
    r = client.get(
        f"/courts/{court.id}/availability",
        params={"day": target.date().isoformat(), "slot_minutes": 60},
        headers=auth(token),
    )
    slots = r.json()
    assert len(slots) == 3  # de 4 queda 1 ocupado
    assert all(not s["start"].startswith(target.isoformat()[:13]) for s in slots)


def test_availability_empty_without_rule_for_that_day(client, db, make_user, login, auth):
    """Sin regla horaria para ese dia, no hay slots."""
    venue = Venue(name="S", address="A", timezone="America/Bogota")
    db.add(venue)
    db.flush()
    court = Court(venue_id=venue.id, name="C")
    db.add(court)
    db.commit()
    db.refresh(court)
    make_user(email="u@example.com", role=UserRole.CLIENT)
    token = login("u@example.com")
    day = (datetime.now(TZ) + timedelta(days=3)).date().isoformat()
    r = client.get(f"/courts/{court.id}/availability", params={"day": day}, headers=auth(token))
    assert r.status_code == 200
    assert r.json() == []
