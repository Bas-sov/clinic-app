from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.doctor import Doctor
    from app.models.patient import Patient


class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    type: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))

    patient: Mapped["Patient"] = relationship(lazy="raise")
    doctor: Mapped["Doctor | None"] = relationship(lazy="raise")
