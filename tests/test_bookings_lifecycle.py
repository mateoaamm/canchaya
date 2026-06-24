"""Tests del ciclo de vida de una reserva y de la gestion por staff/admin."""

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
    return venue, court


def _book(client, token, court_id, auth, hour=10):
    s = (datetime.now(TZ) + timedelta(days=4)).replace(hour=hour, minute=0, second=0, microsecond=0)
    return client.post(
        "/bookings",
        json={
            "court_id": court_id,
            "start_time": s.isoformat(),
            "end_time": (s + timedelta(hours=1)).isoformat(),
        },
        headers=auth(token),
    )


def test_get_venue_404(client, make_user, login, auth):
    make_user(email="u@example.com", role=UserRole.CLIENT)
    token = login("u@example.com")
    assert client.get("/venues/9999", headers=auth(token)).status_code == 404


def test_admin_creates_venue_and_court_then_lists(client, make_user, login, auth):
    make_user(email="admin@example.com", role=UserRole.ADMIN)
    token = login("admin@example.com")
    v = client.post("/venues", json={"name": "Sede", "address": "Calle 1"}, headers=auth(token))
    assert v.status_code == 201
    vid = v.json()["id"]
    c = client.post(
        "/venues/courts", json={"venue_id": vid, "name": "Cancha A"}, headers=auth(token)
    )
    assert c.status_code == 201
    listing = client.get("/courts", params={"venue_id": vid}, headers=auth(token))
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_staff_confirms_payment_sets_booking_confirmed(client, db, make_user, login, auth):
    venue, court = _seed(db)
    make_user(email="client@example.com", role=UserRole.CLIENT)
    make_user(email="staff@example.com", role=UserRole.STAFF, venue_id=venue.id)

    ctoken = login("client@example.com")
    created = _book(client, ctoken, court.id, auth)
    assert created.status_code == 201
    bid = created.json()["id"]
    assert created.json()["status"] == "pending"
    assert created.json()["payment"]["status"] == "pending"

    stoken = login("staff@example.com")
    r = client.post(f"/bookings/{bid}/confirm-payment", headers=auth(stoken))
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"
    assert r.json()["payment"]["status"] == "paid"


def test_client_cannot_confirm_payment(client, db, make_user, login, auth):
    venue, court = _seed(db)
    make_user(email="client@example.com", role=UserRole.CLIENT)
    ctoken = login("client@example.com")
    bid = _book(client, ctoken, court.id, auth).json()["id"]
    # confirm-payment exige STAFF/ADMIN -> 403 para cliente
    assert client.post(f"/bookings/{bid}/confirm-payment", headers=auth(ctoken)).status_code == 403


def test_client_lists_only_own_bookings(client, db, make_user, login, auth):
    venue, court = _seed(db)
    make_user(email="a@example.com", role=UserRole.CLIENT)
    make_user(email="b@example.com", role=UserRole.CLIENT)
    ta, tb = login("a@example.com"), login("b@example.com")
    _book(client, ta, court.id, auth, hour=10)
    _book(client, tb, court.id, auth, hour=12)
    la = client.get("/bookings", headers=auth(ta)).json()
    assert len(la) == 1  # A solo ve la suya


def test_cancel_already_cancelled_conflicts(client, db, make_user, login, auth):
    venue, court = _seed(db)
    make_user(email="u@example.com", role=UserRole.CLIENT)
    t = login("u@example.com")
    bid = _book(client, t, court.id, auth).json()["id"]
    assert client.post(f"/bookings/{bid}/cancel", headers=auth(t)).status_code == 200
    assert client.post(f"/bookings/{bid}/cancel", headers=auth(t)).status_code == 409
