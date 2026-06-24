"""Punto de entrada de la API CanchaYa."""

from fastapi import FastAPI

from app.api.routes import auth, bookings, courts, venues
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.project_name,
    version="0.1.0",
    description="API de reservas de canchas de futbol con rigor profesional.",
)

app.include_router(auth.router)
app.include_router(venues.router)
app.include_router(courts.router)
app.include_router(bookings.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Health check para orquestadores / load balancers."""
    return {"status": "ok"}
