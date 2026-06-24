"""Sedes y canchas. Crear/editar es solo de admin; ver es de cualquier autenticado."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.enums import UserRole
from app.models.court import Court
from app.models.user import User
from app.models.venue import Venue
from app.schemas.court import CourtCreate, CourtOut
from app.schemas.venue import VenueCreate, VenueOut

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueOut])
def list_venues(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[Venue]:
    return list(db.scalars(select(Venue).order_by(Venue.id)))


@router.post("", response_model=VenueOut, status_code=status.HTTP_201_CREATED)
def create_venue(
    data: VenueCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> Venue:
    venue = Venue(**data.model_dump())
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(
    venue_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Venue:
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sede no encontrada")
    return venue


@router.post("/courts", response_model=CourtOut, status_code=status.HTTP_201_CREATED)
def create_court(
    data: CourtCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
) -> Court:
    if db.get(Venue, data.venue_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Sede no encontrada")
    court = Court(**data.model_dump())
    db.add(court)
    db.commit()
    db.refresh(court)
    return court
