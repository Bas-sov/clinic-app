from typing import Literal

from fastapi import APIRouter, status

from app.api.deps import CurrentPatient, PaginationDep, SessionDep
from app.models import CancelInitiator
from app.schemas.appointments import (
    AppointmentDetailOut,
    AppointmentPage,
    BookIn,
    PatientCancelIn,
    RescheduleIn,
)
from app.services import appointments

router = APIRouter(prefix="/patient/appointments", tags=["Пациент: записи"])


@router.get("", response_model=AppointmentPage)
async def list_appointments(
    patient: CurrentPatient,
    session: SessionDep,
    pagination: PaginationDep,
    scope: Literal["upcoming", "past"] = "upcoming",
) -> AppointmentPage:
    return await appointments.patient_list(session, patient.id, scope, pagination.limit, pagination.offset)


@router.get("/{appointment_id}", response_model=AppointmentDetailOut)
async def get_appointment(appointment_id: int, patient: CurrentPatient, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.patient_detail(session, patient.id, appointment_id)


@router.post("", response_model=AppointmentDetailOut, status_code=status.HTTP_201_CREATED)
async def book(data: BookIn, patient: CurrentPatient, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.book(session, patient.id, data.schedule_id, data.service_id, by_admin=False)


@router.post("/{appointment_id}/cancel", response_model=AppointmentDetailOut)
async def cancel(
    appointment_id: int, data: PatientCancelIn, patient: CurrentPatient, session: SessionDep
) -> AppointmentDetailOut:
    return await appointments.cancel(
        session, appointment_id, reason=data.reason, by=CancelInitiator.PATIENT, patient_id=patient.id
    )


@router.post("/{appointment_id}/reschedule", response_model=AppointmentDetailOut)
async def reschedule(
    appointment_id: int, data: RescheduleIn, patient: CurrentPatient, session: SessionDep
) -> AppointmentDetailOut:
    return await appointments.reschedule(session, appointment_id, data.schedule_id, patient_id=patient.id)
