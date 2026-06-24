"""Configuracion de pytest.

Decision clave: los tests corren contra PostgreSQL real (no SQLite), porque el
corazon del proyecto (EXCLUDE constraint, tstzrange, btree_gist) es especifico
de Postgres. Testear contra una BD distinta a produccion oculta justo los bugs
que mas importan. CI levanta un service de Postgres identico.

Esquema: se crea una vez por sesion via migraciones de Alembic (mismo camino
que produccion). Entre tests truncamos las tablas para aislamiento.
"""

import os

# IMPORTANTE: fijar la BD de test ANTES de importar la app (las env vars tienen
# prioridad sobre el archivo .env en pydantic-settings).
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://canchaya:canchaya@localhost:5432/canchaya_test",
)

import pytest  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.database import SessionLocal, engine  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.enums import UserRole  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402

get_settings.cache_clear()

_TABLES = (
    "payments",
    "bookings",
    "availability_rules",
    "courts",
    "refresh_tokens",
    "users",
    "venues",
)


@pytest.fixture(scope="session", autouse=True)
def _migrate() -> None:
    """Crea el esquema completo via Alembic una vez por sesion."""
    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")  # idempotente: parte de cero
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables() -> None:
    """Vacia las tablas despues de cada test para aislarlos."""
    yield
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {', '.join(_TABLES)} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ---- Helpers de usuarios/tokens -----------------------------------------


def _make_user(db, email, role=UserRole.CLIENT, venue_id=None, password="secret123"):
    user = User(
        email=email,
        hashed_password=hash_password(password),
        full_name=email.split("@")[0],
        role=role,
        venue_id=venue_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _login(client, email, password="secret123") -> str:
    resp = client.post("/auth/login", data={"username": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_user(db):
    return lambda **kw: _make_user(db, **kw)


@pytest.fixture
def login(client):
    return lambda email, password="secret123": _login(client, email, password)


@pytest.fixture
def auth():
    return _auth
