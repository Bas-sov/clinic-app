from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentDoctor, SessionDep
from app.schemas.appointments import AppointmentDetailOut, CompleteIn, DayLoadOut, DoctorAppointmentOut
from app.services import appointments

router = APIRouter(prefix="/doctor/appointments", tags=["Врач: приёмы"])


@router.get("", response_model=list[DoctorAppointmentOut])
async def day_queue(doctor: CurrentDoctor, session: SessionDep, on_date: date | None = None) -> list[DoctorAppointmentOut]:
    return await appointments.doctor_day(session, doctor.id, on_date)


@router.get("/month", response_model=list[DayLoadOut])
async def month_load(month: str, doctor: CurrentDoctor, session: SessionDep) -> list[DayLoadOut]:
    return await appointments.doctor_month(session, doctor.id, month)


@router.get("/{appointment_id}", response_model=DoctorAppointmentOut)
async def get_appointment(appointment_id: int, doctor: CurrentDoctor, session: SessionDep) -> DoctorAppointmentOut:
    return await appointments.doctor_detail(session, doctor.id, appointment_id)


@router.post("/{appointment_id}/start", response_model=DoctorAppointmentOut)
async def start(appointment_id: int, doctor: CurrentDoctor, session: SessionDep) -> DoctorAppointmentOut:
    return await appointments.start(session, appointment_id, doctor.id)


@router.post("/{appointment_id}/no-show", response_model=AppointmentDetailOut)
async def no_show(appointment_id: int, doctor: CurrentDoctor, session: SessionDep) -> AppointmentDetailOut:
    return await appointments.mark_no_show(session, appointment_id, doctor_id=doctor.id)


@router.post("/{appointment_id}/complete", response_model=AppointmentDetailOut)
async def complete(
    appointment_id: int, data: CompleteIn, doctor: CurrentDoctor, session: SessionDep
) -> AppointmentDetailOut:
    return await appointments.complete(session, appointment_id, doctor.id, data)
