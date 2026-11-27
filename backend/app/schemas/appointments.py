from datetime import date, datetime, time
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AppointmentStatus, CancelInitiator, ServiceCategory

VisitType = Literal["first", "repeat"]


class _Orm(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SlotBrief(_Orm):
    id: int
    work_date: date
    start_time: time
    end_time: time
    cabinet: str


class ServiceBrief(_Orm):
    id: int
    name: str
    category: ServiceCategory
    duration_minutes: int
    preparation: str | None


class DoctorBrief(BaseModel):
    id: int
    last_name: str
    first_name: str
    middle_name: str | None
    specialty: str


class PatientBrief(BaseModel):
    id: int
    last_name: str
    first_name: str
    middle_name: str | None
    phone: str | None
    age: int | None
    medical_card_number: str


class PrescriptionOut(_Orm):
    id: int
    prescription_date: date
    valid_until: date | None
    medicine: str
    dosage: str | None
    instructions: str | None


class AppointmentOut(BaseModel):
    id: int
    status: AppointmentStatus
    price: Decimal
    created_at: datetime
    slot: SlotBrief
    service: ServiceBrief
    doctor: DoctorBrief | None
    patient: PatientBrief | None = None
    cancel_reason: str | None
    canceled_at: datetime | None
    canceled_by: CancelInitiator | None
    conclusion: str | None


class AppointmentDetailOut(AppointmentOut):
    prescriptions: list[PrescriptionOut]


class DoctorAppointmentOut(AppointmentOut):
    visit_type: VisitType
    previous_visit_date: date | None


class AppointmentPage(BaseModel):
    items: list[AppointmentOut]
    total: int


class DayLoadOut(BaseModel):
    work_date: date
    appointments: int


class BookIn(BaseModel):
    schedule_id: int
    service_id: int


class AdminBookIn(BookIn):
    patient_id: int


class RescheduleIn(BaseModel):
    schedule_id: int


class PatientCancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class AdminCancelIn(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Укажите причину отмены")
        return value


class PrescriptionIn(BaseModel):
    medicine: str = Field(min_length=1, max_length=255)
    dosage: str | None = Field(default=None, max_length=100)
    instructions: str | None = None
    valid_until: date | None = None


class CompleteIn(BaseModel):
    conclusion: str = Field(min_length=1)
    prescriptions: list[PrescriptionIn] = Field(default_factory=list, max_length=20)

    @field_validator("conclusion")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Заключение не может быть пустым")
        return value
