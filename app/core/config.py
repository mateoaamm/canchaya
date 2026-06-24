"""Configuracion de la app leida desde variables de entorno (.env).

Regla profesional: NUNCA credenciales hardcodeadas en el codigo.
Todo lo sensible entra por entorno. pydantic-settings valida tipos al arrancar,
asi un .env mal puesto falla de inmediato y no a mitad de un request.
"""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Base de datos
    database_url: str = "postgresql+psycopg://canchaya:canchaya@localhost:5432/canchaya"

    @field_validator("database_url")
    @classmethod
    def _normalize_db_scheme(cls, v: str) -> str:
        """Acepta la URL que dan Render/Railway ('postgresql://') y le pone el
        driver explicito que usa SQLAlchemy ('postgresql+psycopg://')."""
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg://", 1)
        return v

    # Seguridad / JWT
    secret_key: str = "CAMBIAME-en-produccion-usa-un-secreto-largo-y-aleatorio"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # App
    project_name: str = "CanchaYa"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    """Cacheada para no releer el entorno en cada request."""
    return Settings()
