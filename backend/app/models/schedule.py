from datetime import date, time
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Identity, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SlotStatus, slot_status_type

if TYPE_CHECKING:
    from app.models.doctor import Doctor


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    cabinet: Mapped[str] = mapped_column(String(20))
    work_date: Mapped[date] = mapped_column(Date)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    status: Mapped[SlotStatus] = mapped_column(
        slot_status_type, server_default=SlotStatus.FREE.value
    )

    doctor: Mapped["Doctor | None"] = relationship(lazy="raise")
