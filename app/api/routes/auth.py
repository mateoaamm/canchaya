"""Endpoints de autenticacion: register, login, refresh (con rotacion), logout."""

from datetime import UTC, datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.enums import UserRole
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.schemas.auth import AccessTokenOut, RefreshIn, RegisterIn, TokenPair
from app.schemas.user import UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_pair(db: Session, user: User) -> TokenPair:
    access = create_access_token(str(user.id), user.role.value)
    refresh, jti, expires = create_refresh_token(str(user.id))
    db.add(RefreshToken(jti=jti, user_id=user.id, expires_at=expires))
    db.commit()
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(data: RegisterIn, db: Session = Depends(get_db)) -> User:
    """Registro abierto: siempre crea un CLIENTE. Staff/admin los crea un admin."""
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "El email ya esta registrado")
    user = User(
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.CLIENT,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenPair)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenPair:
    """OAuth2 password flow: 'username' es el email."""
    user = db.scalar(select(User).where(User.email == form.username))
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Email o contrasena incorrectos")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Usuario inactivo")
    return _issue_pair(db, user)


@router.post("/refresh", response_model=AccessTokenOut)
def refresh(data: RefreshIn, db: Session = Depends(get_db)) -> AccessTokenOut:
    """Entrega un nuevo access token si el refresh es valido y NO fue revocado."""
    try:
        payload = decode_token(data.refresh_token)
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token invalido") from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Tipo de token incorrecto")

    jti = payload.get("jti")
    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == jti))
    if record is None or record.revoked:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesion revocada o inexistente")
    if record.expires_at < datetime.now(UTC):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expirado")

    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no valido")

    return AccessTokenOut(access_token=create_access_token(str(user.id), user.role.value))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: RefreshIn, db: Session = Depends(get_db)) -> None:
    """Revoca el refresh token. A partir de aqui /refresh con el devuelve 401."""
    try:
        payload = decode_token(data.refresh_token)
    except jwt.PyJWTError:
        return  # token basura: nada que revocar, igual respondemos 204
    record = db.scalar(select(RefreshToken).where(RefreshToken.jti == payload.get("jti")))
    if record and not record.revoked:
        record.revoked = True
        db.commit()


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user
