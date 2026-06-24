"""Carga datos de ejemplo para probar la API rápidamente.

Crea un admin, un staff, un cliente, una sede con una cancha y horarios de
atención. Idempotente: si el admin ya existe, no hace nada.

Uso:  python -m scripts.seed   (o: make seed)
"""

from datetime import time

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.enums import Surface, UserRole
from app.models.availability import AvailabilityRule
from app.models.court import Court
from app.models.user import User
from app.models.venue import Venue


def run() -> None:
    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.email == "admin@canchaya.co")):
            print("Los datos de ejemplo ya existen. Nada que hacer.")
            return

        venue = Venue(
            name="Sede Pereira Centro",
            address="Cra 7 #20-30, Pereira",
            timezone="America/Bogota",
        )
        db.add(venue)
        db.flush()

        court = Court(venue_id=venue.id, name="Cancha 1", surface=Surface.SYNTHETIC)
        db.add(court)
        db.flush()

        # Atiende todos los días de 08:00 a 22:00
        for weekday in range(7):
            db.add(
                AvailabilityRule(
                    court_id=court.id,
                    weekday=weekday,
                    open_time=time(8, 0),
                    close_time=time(22, 0),
                )
            )

        db.add_all(
            [
                User(
                    email="admin@canchaya.co",
                    hashed_password=hash_password("admin1234"),
                    full_name="Admin",
                    role=UserRole.ADMIN,
                ),
                User(
                    email="staff@canchaya.co",
                    hashed_password=hash_password("staff1234"),
                    full_name="Staff Centro",
                    role=UserRole.STAFF,
                    venue_id=venue.id,
                ),
                User(
                    email="cliente@canchaya.co",
                    hashed_password=hash_password("cliente1234"),
                    full_name="Cliente Demo",
                    role=UserRole.CLIENT,
                ),
            ]
        )
        db.commit()
        print("Datos de ejemplo cargados:")
        print("  admin@canchaya.co   / admin1234")
        print("  staff@canchaya.co   / staff1234")
        print("  cliente@canchaya.co / cliente1234")
        print(f"  Sede '{venue.name}' con cancha '{court.name}' (08:00-22:00 todos los días)")
    finally:
        db.close()


if __name__ == "__main__":
    run()
