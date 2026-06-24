"""Utilidades de seguridad: hashing de contrasenas y tokens JWT.

Estrategia de tokens:
  - access token: corto (minutos). Se manda en cada request. Si se filtra, caduca rapido.
  - refresh token: largo (dias). Solo sirve para pedir un nuevo access token.
    Lleva un 'jti' (id unico) que guardamos en BD para poder REVOCARLO en logout.
    Por eso el logout de verdad invalida la sesion (testeable), en vez de
    confiar en que el cliente "olvide" el token.
"""

import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


# ---- Passwords -----------------------------------------------------------


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---- Tokens --------------------------------------------------------------


def create_access_token(subject: str, role: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_refresh_token(subject: str) -> tuple[str, str, datetime]:
    """Devuelve (token, jti, expira_en). El jti se persiste para poder revocar."""
    now = datetime.now(UTC)
    expires = now + timedelta(days=settings.refresh_token_expire_days)
    jti = str(uuid.uuid4())
    payload = {"sub": subject, "type": "refresh", "jti": jti, "iat": now, "exp": expires}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, jti, expires


def decode_token(token: str) -> dict:
    """Decodifica y valida firma + expiracion. Lanza jwt.PyJWTError si es invalido."""
    return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
