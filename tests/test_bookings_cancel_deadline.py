"""Amenaza T2 del Lab 1: cancelar un partido ya jugado dejaba el pago como REFUNDED.

Requisito: un cliente solo cancela hasta 2 horas antes de start_time; despues la API
responde 409 y ni la reserva ni el pago cambian. ASVS 5.0: 2.3.1 y 2.3.2.
El staff y el admin no tienen ese limite (su rastro es la amenaza T7).
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.enums import BookingStatus, PaymentStatus, UserRole
from app.models.booking import Booking
from app.models.court import Court
from app.models.payment import Payment
from app.models.venue import Venue


def _paid_booking(db, user_id, starts_in):
    """Crea directo en BD una reserva confirmada y pagada que empieza en `starts_in`."""
    venue = Venue(name="Sede", address="Cra 1", timezone="America/Bogota")
    db.add(venue)
    db.flush()
    court = Court(venue_id=venue.id, name="C1")
    db.add(court)
    db.flush()
    start = datetime.now(UTC) + starts_in
    booking = Booking(
        court_id=court.id,
        user_id=user_id,
        start_time=start,
        end_time=start + timedelta(hours=1),
        status=BookingStatus.CONFIRMED,
    )
    booking.payment = Payment(amount=Decimal("80000.00"), status=PaymentStatus.PAID)
    db.add(booking)
    db.commit()
    return venue.id, booking.id


def _state(db, booking_id):
    """Estado actual en BD (sin cache de la sesion) de la reserva y su pago."""
    db.expire_all()
    booking = db.get(Booking, booking_id)
    return booking.status, booking.payment.status


def test_client_cannot_cancel_already_played_booking(client, db, make_user, login, auth):
    user = make_user(email="cliente@example.com", role=UserRole.CLIENT)
    _, bid = _paid_booking(db, user.id, starts_in=timedelta(days=-1))
    token = login("cliente@example.com")

    r = client.post(f"/bookings/{bid}/cancel", headers=auth(token))

    assert r.status_code == 409
    assert _state(db, bid) == (BookingStatus.CONFIRMED, PaymentStatus.PAID)


def test_client_cannot_cancel_inside_deadline(client, db, make_user, login, auth):
    user = make_user(email="cliente@example.com", role=UserRole.CLIENT)
    _, bid = _paid_booking(db, user.id, starts_in=timedelta(hours=1))
    token = login("cliente@example.com")

    r = client.post(f"/bookings/{bid}/cancel", headers=auth(token))

    assert r.status_code == 409
    assert _state(db, bid) == (BookingStatus.CONFIRMED, PaymentStatus.PAID)


def test_client_cancels_before_deadline_and_gets_refund(client, db, make_user, login, auth):
    user = make_user(email="cliente@example.com", role=UserRole.CLIENT)
    _, bid = _paid_booking(db, user.id, starts_in=timedelta(days=3))
    token = login("cliente@example.com")

    r = client.post(f"/bookings/{bid}/cancel", headers=auth(token))

    assert r.status_code == 200
    assert _state(db, bid) == (BookingStatus.CANCELLED, PaymentStatus.REFUNDED)


def test_staff_can_cancel_after_start(client, db, make_user, login, auth):
    user = make_user(email="cliente@example.com", role=UserRole.CLIENT)
    venue_id, bid = _paid_booking(db, user.id, starts_in=timedelta(days=-1))
    make_user(email="staff@example.com", role=UserRole.STAFF, venue_id=venue_id)
    token = login("staff@example.com")

    r = client.post(f"/bookings/{bid}/cancel", headers=auth(token))

    assert r.status_code == 200
