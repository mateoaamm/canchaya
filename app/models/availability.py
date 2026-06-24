from datetime import time
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.court import Court


class AvailabilityRule(Base):
    """Horario de atencion de una cancha por dia de la semana.

    weekday: 0=lunes ... 6=domingo (convencion de Python date.weekday()).
    Una reserva solo es valida si cae dentro de [open_time, close_time) del
    weekday correspondiente. Las horas se interpretan en la TZ de la sede.
    """

    __tablename__ = "availability_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    court_id: Mapped[int] = mapped_column(ForeignKey("courts.id"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0..6
    open_time: Mapped[time] = mapped_column(Time, nullable=False)
    close_time: Mapped[time] = mapped_column(Time, nullable=False)

    court: Mapped["Court"] = relationship(back_populates="availability_rules")
