"""Tests de autorizacion (RBAC) y aislamiento por ownership.

El test estrella de seguridad: un cliente NO puede ver la reserva de otro
(prevencion de IDOR, uno de los bugs mas comunes y graves en produccion).
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.enums import UserRole
from app.models.availability import AvailabilityRule
from app.models.court import Court
from app.models.venue import Venue

TZ = ZoneInfo("America/Bogota")


def _seed_court(db) -> Court:
    venue = Venue(name="Sede Centro", address="Cra 1", timezone="America/Bogota")
    db.add(venue)
    db.flush()
    court = Court(venue_id=venue.id, name="Cancha 1")
    db.add(court)
    db.flush()
    # Abre todos los dias 08:00-22:00
    for wd in range(7):
        db.add(
            AvailabilityRule(court_id=court.id, weekday=wd, open_time=time(8), close_time=time(22))
        )
    db.commit()
    db.refresh(court)
    return court


def _next_slot():
    """Un slot de 1h en horario de atencion, en el futuro."""
    base = (datetime.now(TZ) + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    return base, base + timedelta(hours=1)


def test_client_cannot_create_venue(client, make_user, login, auth):
    make_user(email="c@example.com", role=UserRole.CLIENT)
    token = login("c@example.com")
    r = client.post("/venues", json={"name": "X", "address": "Y"}, headers=auth(token))
    assert r.status_code == 403


def test_admin_can_create_venue(client, make_user, login, auth):
    make_user(email="admin@example.com", role=UserRole.ADMIN)
    token = login("admin@example.com")
    r = client.post("/venues", json={"name": "Sede", "address": "Calle"}, headers=auth(token))
    assert r.status_code == 201


def test_client_cannot_see_other_clients_booking(client, db, make_user, login, auth):
    """IDOR: el cliente B pide la reserva del cliente A -> 404 (no se la mostramos)."""
    court = _seed_court(db)
    make_user(email="a@example.com", role=UserRole.CLIENT)
    make_user(email="b@example.com", role=UserRole.CLIENT)

    token_a = login("a@example.com")
    start, end = _next_slot()
    created = client.post(
        "/bookings",
        json={
            "court_id": court.id,
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
        headers=auth(token_a),
    )
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]

    token_b = login("b@example.com")
    r = client.get(f"/bookings/{booking_id}", headers=auth(token_b))
    assert r.status_code == 404  # B no debe poder acceder a la reserva de A

    # A si la ve
    assert client.get(f"/bookings/{booking_id}", headers=auth(token_a)).status_code == 200


def test_staff_only_sees_own_venue_court_bookings(client, db, make_user, login, auth):
    court = _seed_court(db)  # pertenece a la sede 1
    # Una segunda sede, con su propio staff
    other_venue = Venue(name="Sede Norte", address="Cra 99", timezone="America/Bogota")
    db.add(other_venue)
    db.commit()
    db.refresh(other_venue)

    # staff de OTRA sede no puede ver las reservas de esta cancha
    make_user(email="staff_other@example.com", role=UserRole.STAFF, venue_id=other_venue.id)
    token = login("staff_other@example.com")
    r = client.get(f"/courts/{court.id}/bookings", headers=auth(token))
    assert r.status_code == 403

    # staff de la sede correcta si puede
    make_user(email="staff_ok@example.com", role=UserRole.STAFF, venue_id=court.venue_id)
    token_ok = login("staff_ok@example.com")
    assert client.get(f"/courts/{court.id}/bookings", headers=auth(token_ok)).status_code == 200
