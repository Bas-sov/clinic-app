from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, ForeignKeyConstraint, Identity, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AnalysisStatus, analysis_status_type

if TYPE_CHECKING:
    from app.models.appointment import Appointment
    from app.models.doctor import Doctor
    from app.models.patient import Patient


class Analysis(Base):
    __tablename__ = "analyses"
    # Составной ключ из схемы: анализ можно привязать только к приёму того же пациента.
    __table_args__ = (
        ForeignKeyConstraint(
            ["appointment_id", "patient_id"],
            ["appointments.id", "appointments.patient_id"],
        ),
    )

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    appointment_id: Mapped[int | None]
    doctor_id: Mapped[int | None] = mapped_column(ForeignKey("doctors.id"))
    name: Mapped[str] = mapped_column(String(255))
    analysis_date: Mapped[date] = mapped_column(Date)
    status: Mapped[AnalysisStatus] = mapped_column(
        analysis_status_type, server_default=AnalysisStatus.PROCESSING.value
    )
    result: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))
    comment: Mapped[str | None] = mapped_column(Text)

    patient: Mapped["Patient"] = relationship(lazy="raise")
    doctor: Mapped["Doctor | None"] = relationship(lazy="raise")
    # viewonly: patient_id входит в оба ключа, связь только для чтения
    # убирает конфликт; привязку задаём через appointment_id.
    appointment: Mapped["Appointment | None"] = relationship(
        viewonly=True, lazy="raise"
    )
