"""Anti-doble-reserva a nivel de base de datos (EXCLUDE constraint).

Esta es la pieza central del proyecto. El chequeo en codigo (booking_service)
puede perder la carrera si dos requests llegan simultaneamente: ambos consultan,
ambos ven el horario libre, ambos insertan. El 'if' en Python NO protege bajo
concurrencia.

La garantia real la da Postgres con un EXCLUDE constraint usando un indice GiST:
no pueden coexistir dos filas con el MISMO court_id y rangos de tiempo que se
SOLAPEN (&&), salvo las canceladas (clausula WHERE parcial).

Requiere la extension btree_gist para poder combinar la igualdad de court_id
(tipo escalar) con el operador de solapamiento de rangos en el mismo indice.

Revision ID: a1b2c3d4e5f6
Revises: e41ce2073d27
Create Date: 2026-06-24
"""
from collections.abc import Sequence

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "3780d53e8e4a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONSTRAINT_NAME = "no_double_booking"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    op.execute(
        f"""
        ALTER TABLE bookings
        ADD CONSTRAINT {CONSTRAINT_NAME}
        EXCLUDE USING gist (
            court_id WITH =,
            tstzrange(start_time, end_time, '[)') WITH &&
        )
        WHERE (status <> 'cancelled');
        """
    )


def downgrade() -> None:
    op.execute(f"ALTER TABLE bookings DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME};")
    # No quitamos btree_gist: otras cosas podrian depender de ella.
