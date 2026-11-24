from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Identity, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.patient import Patient


class SickLeave(Base):
    __tablename__ = "sick_leaves"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    number: Mapped[str | None] = mapped_column(String(50), unique=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    diagnosis: Mapped[str | None] = mapped_column(String(255))
    file_path: Mapped[str | None] = mapped_column(String(500))

    patient: Mapped["Patient"] = relationship(lazy="raise")
    doctor: Mapped["Doctor | None"] = relationship(lazy="raise")
