"""Amenaza T1 del Lab 1: el seed crea cuentas con contrasenas publicadas en el repo.

En julio se cargo en produccion corriendolo desde el portatil con la URL externa de
Render. Requisito: el seed se niega a correr con APP_ENV=production o contra una base
que no sea local, y lo hace antes de abrir cualquier sesion. ASVS 5.0: 6.3.2 y 15.2.3.
"""

import pytest

from app.core.config import get_settings
from scripts import seed

REMOTE_URL = "postgresql://canchaya:x@dpg-ejemplo.oregon-postgres.render.com/canchaya"
LOCAL_URL = "postgresql+psycopg://canchaya:canchaya@localhost:5432/canchaya"


class _FakeSession:
    """Simula que los datos ya existen: el seed termina sin escribir nada."""

    def scalar(self, *_args):
        return object()

    def close(self):
        pass


@pytest.fixture
def opened(monkeypatch):
    """Registra cada sesion de BD que el seed intente abrir."""
    calls = []

    def fake_session_local():
        calls.append(1)
        return _FakeSession()

    monkeypatch.setattr(seed, "SessionLocal", fake_session_local)
    get_settings.cache_clear()
    yield calls
    get_settings.cache_clear()


def test_seed_refuses_production_env(opened, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)

    with pytest.raises(SystemExit):
        seed.run()

    assert opened == []


def test_seed_refuses_remote_database(opened, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", REMOTE_URL)

    with pytest.raises(SystemExit):
        seed.run()

    assert opened == []


def test_seed_runs_against_local_database(opened, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", LOCAL_URL)

    seed.run()

    assert opened == [1]
