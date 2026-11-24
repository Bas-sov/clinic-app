from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Identity, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.appointment import Appointment


class Prescription(Base):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    appointment_id: Mapped[int] = mapped_column(ForeignKey("appointments.id"))
    prescription_date: Mapped[date] = mapped_column(
        Date, server_default=func.current_date()
    )
    valid_until: Mapped[date | None] = mapped_column(Date)
    medicine: Mapped[str] = mapped_column(String(255))
    dosage: Mapped[str | None] = mapped_column(String(100))
    instructions: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))

    appointment: Mapped["Appointment"] = relationship(
        back_populates="prescriptions", lazy="raise"
    )
