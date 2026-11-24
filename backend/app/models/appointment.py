from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, Numeric, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AppointmentStatus,
    CancelInitiator,
    appointment_status_type,
    cancel_initiator_type,
)

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.prescription import Prescription
    from app.models.schedule import Schedule
    from app.models.service import Service


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"))
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedule.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    status: Mapped[AppointmentStatus] = mapped_column(
        appointment_status_type, server_default=AppointmentStatus.PLANNED.value
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text)
    canceled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    canceled_by: Mapped[CancelInitiator | None] = mapped_column(cancel_initiator_type)
    conclusion: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    patient: Mapped["Patient"] = relationship(lazy="raise")
    schedule: Mapped["Schedule"] = relationship(lazy="raise")
    service: Mapped["Service"] = relationship(lazy="raise")
    prescriptions: Mapped[list["Prescription"]] = relationship(
        back_populates="appointment", lazy="raise"
    )
