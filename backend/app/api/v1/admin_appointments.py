from datetime import date

from fastapi import APIRouter, Depends, status

from app.api.deps import PaginationDep, SessionDep, require_role
from app.models import AppointmentStatus, CancelInitiator
from app.schemas.appointments import (
    AdminBookIn,
    AdminCancelIn,
    AppointmentDetailOut,
    AppointmentPage,
    RescheduleIn,
)
from app.services import appointments

router = APIRouter(
    prefix="/admin/appointments", tags=["Админ: записи"], dependencies=[Depends(require_role("admin"))]
)


@router.get("", response_model=AppointmentPage)
async def list_appointments(
    session: SessionDep,
    pagination: PaginationDep,
    on_date: date | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    doctor_id: int | None = None,
    cabinet: str | None = None,
    patient_id: int | None = None,
    appointment_status: AppointmentStatus | None = None,
) -> AppointmentPage:
    return await appointments.admin_list(
        session,
        pagination.limit,
        pagination.offset,
        on_date=on_date,
        date_from=date_from,
        date_to=date_to,
        doctor_id=doctor_id,
        cabinet=cabinet,
        patient_id=patient_id,
        status=appointment_status,
    )


@router.get("/{appointment_id}", response_model=AppointmentDetailOut)
async def get_appointment(appointment_id: int, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.admin_detail(session, appointment_id)


@router.post("", response_model=AppointmentDetailOut, status_code=status.HTTP_201_CREATED)
async def book(data: AdminBookIn, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.book(session, data.patient_id, data.schedule_id, data.service_id, by_admin=True)


@router.post("/{appointment_id}/cancel", response_model=AppointmentDetailOut)
async def cancel(appointment_id: int, data: AdminCancelIn, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.cancel(session, appointment_id, reason=data.reason, by=CancelInitiator.ADMINISTRATOR)


@router.post("/{appointment_id}/reschedule", response_model=AppointmentDetailOut)
async def reschedule(appointment_id: int, data: RescheduleIn, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.reschedule(session, appointment_id, data.schedule_id)


@router.post("/{appointment_id}/attended", response_model=AppointmentDetailOut)
async def attended(appointment_id: int, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.mark_attended_no_doctor(session, appointment_id)


@router.post("/{appointment_id}/no-show", response_model=AppointmentDetailOut)
async def no_show(appointment_id: int, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.mark_no_show(session, appointment_id)
