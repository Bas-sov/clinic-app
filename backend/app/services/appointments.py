from datetime import UTC, date, datetime, timedelta
from typing import Literal

from sqlalchemy import and_, func, select, tuple_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import (
    Analysis,
    AnalysisStatus,
    Appointment,
    AppointmentStatus,
    CancelInitiator,
    Doctor,
    Patient,
    Prescription,
    Schedule,
    Service,
    ServiceCategory,
    SlotStatus,
)
from app.schemas.appointments import (
    AppointmentDetailOut,
    AppointmentOut,
    AppointmentPage,
    CompleteIn,
    DayLoadOut,
    DoctorAppointmentOut,
    DoctorBrief,
    PatientBrief,
    PrescriptionOut,
    ServiceBrief,
    SlotBrief,
)

MAX_ACTIVE_PER_PATIENT = 5
PATIENT_CANCEL_REASON = "Отменено пациентом"
NO_DOCTOR_CONCLUSION = "Услуга оказана"

_FULL_LOAD = (
    selectinload(Appointment.schedule).selectinload(Schedule.doctor).selectinload(Doctor.specialty),
    selectinload(Appointment.service),
    selectinload(Appointment.patient),
)


def _now() -> datetime:
    """Текущее время клиники без часового пояса — так же хранится расписание."""
    return datetime.now(get_settings().clinic_tz).replace(tzinfo=None)


def _slot_start(slot: Schedule) -> datetime:
    return datetime.combine(slot.work_date, slot.start_time)


def _slot_after(moment: datetime):
    return tuple_(Schedule.work_date, Schedule.start_time) > tuple_(moment.date(), moment.time())


# ---------- Сборка ответов ----------


def _age(birth: date | None, today: date) -> int | None:
    if birth is None:
        return None
    return today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))


def _patient_brief(patient: Patient) -> PatientBrief:
    return PatientBrief(
        id=patient.id,
        last_name=patient.last_name,
        first_name=patient.first_name,
        middle_name=patient.middle_name,
        phone=patient.phone,
        age=_age(patient.birth_date, _now().date()),
        medical_card_number=f"{patient.id:05d}",
    )


def _to_out(a: Appointment, with_patient: bool) -> dict:
    doctor = a.schedule.doctor
    return dict(
        id=a.id,
        status=a.status,
        price=a.price,
        created_at=a.created_at,
        slot=SlotBrief.model_validate(a.schedule),
        service=ServiceBrief.model_validate(a.service),
        doctor=None
        if doctor is None
        else DoctorBrief(
            id=doctor.id,
            last_name=doctor.last_name,
            first_name=doctor.first_name,
            middle_name=doctor.middle_name,
            specialty=doctor.specialty.name,
        ),
        patient=_patient_brief(a.patient) if with_patient else None,
        cancel_reason=a.cancel_reason,
        canceled_at=a.canceled_at,
        canceled_by=a.canceled_by,
        conclusion=a.conclusion,
    )


async def _detail(session: AsyncSession, a: Appointment, with_patient: bool) -> AppointmentDetailOut:
    rows = await session.scalars(
        select(Prescription).where(Prescription.appointment_id == a.id).order_by(Prescription.id)
    )
    return AppointmentDetailOut(
        **_to_out(a, with_patient), prescriptions=[PrescriptionOut.model_validate(p) for p in rows]
    )


async def _previous_visit(session: AsyncSession, a: Appointment) -> date | None:
    """Дата последнего завершённого приёма у врача той же специальности до этой записи."""
    doctor = a.schedule.doctor
    if doctor is None:
        return None
    return await session.scalar(
        select(func.max(Schedule.work_date))
        .select_from(Appointment)
        .join(Schedule, Schedule.id == Appointment.schedule_id)
        .join(Doctor, Doctor.id == Schedule.doctor_id)
        .where(
            Appointment.patient_id == a.patient_id,
            Appointment.status == AppointmentStatus.COMPLETED,
            Doctor.specialty_id == doctor.specialty_id,
            Appointment.id != a.id,
            tuple_(Schedule.work_date, Schedule.start_time)
            < tuple_(a.schedule.work_date, a.schedule.start_time),
        )
    )


async def _doctor_out(session: AsyncSession, a: Appointment) -> DoctorAppointmentOut:
    previous = await _previous_visit(session, a)
    return DoctorAppointmentOut(
        **_to_out(a, with_patient=True),
        visit_type="repeat" if previous else "first",
        previous_visit_date=previous,
    )


# ---------- Загрузка с проверкой доступа ----------


async def _load(
    session: AsyncSession,
    appointment_id: int,
    *,
    patient_id: int | None = None,
    doctor_id: int | None = None,
    lock: bool = False,
) -> Appointment:
    # populate_existing: объекты уже могут быть в сессии без связей (например, новый слот после переноса).
    stmt = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(*_FULL_LOAD)
        .execution_options(populate_existing=True)
    )
    if lock:
        stmt = stmt.with_for_update(of=Appointment)
    a = await session.scalar(stmt)
    # Чужая запись выглядит как несуществующая — не раскрываем, что она есть.
    if (
        a is None
        or (patient_id is not None and a.patient_id != patient_id)
        or (doctor_id is not None and a.schedule.doctor_id != doctor_id)
    ):
        raise NotFoundError("appointment_not_found", "Запись не найдена")
    return a


async def _lock_slot(session: AsyncSession, slot_id: int) -> Schedule:
    slot = await session.get(Schedule, slot_id, with_for_update=True, populate_existing=True)
    if slot is None:
        raise NotFoundError("slot_not_found", "Слот не найден")
    return slot


def _require_status(a: Appointment, *allowed: AppointmentStatus) -> None:
    if a.status not in allowed:
        raise BadRequestError("invalid_status", "Действие недоступно для записи в текущем статусе")


# ---------- Запись ----------


async def _check_patient_free(session: AsyncSession, patient_id: int, slot: Schedule, exclude_id: int | None) -> None:
    stmt = (
        select(Appointment.id)
        .join(Schedule, Schedule.id == Appointment.schedule_id)
        .where(
            Appointment.patient_id == patient_id,
            Appointment.status.in_([AppointmentStatus.PLANNED, AppointmentStatus.IN_PROGRESS]),
            Schedule.work_date == slot.work_date,
            Schedule.start_time < slot.end_time,
            Schedule.end_time > slot.start_time,
        )
    )
    if exclude_id is not None:
        stmt = stmt.where(Appointment.id != exclude_id)
    if await session.scalar(stmt.limit(1)):
        raise ConflictError("patient_time_conflict", "У пациента уже есть запись на это время")


async def _check_service_fits(session: AsyncSession, slot: Schedule, service: Service) -> None:
    if slot.doctor_id is not None:
        doctor = await session.get(Doctor, slot.doctor_id)
        fits = (
            doctor is not None
            and doctor.is_active
            and service.category == ServiceCategory.CONSULTATION
            and service.specialty_id == doctor.specialty_id
        )
    else:
        fits = service.category in (ServiceCategory.ANALYSIS, ServiceCategory.PROCEDURE)
    if not fits:
        raise BadRequestError("service_slot_mismatch", "Эта услуга недоступна в выбранном слоте")


async def book(
    session: AsyncSession, patient_id: int, schedule_id: int, service_id: int, *, by_admin: bool
) -> AppointmentDetailOut:
    now = _now()
    slot = await _lock_slot(session, schedule_id)
    if slot.status != SlotStatus.FREE:
        raise ConflictError("slot_unavailable", "Слот уже занят или закрыт")
    if _slot_start(slot) <= now:
        raise BadRequestError("slot_in_past", "Нельзя записаться на прошедшее время")

    service = await session.get(Service, service_id)
    if service is None or (not service.is_visible and not by_admin):
        raise NotFoundError("service_not_found", "Услуга не найдена")
    await _check_service_fits(session, slot, service)

    if by_admin and await session.get(Patient, patient_id) is None:
        raise NotFoundError("patient_not_found", "Пациент не найден")
    await _check_patient_free(session, patient_id, slot, exclude_id=None)

    if not by_admin:
        active = await session.scalar(
            select(func.count())
            .select_from(Appointment)
            .join(Schedule, Schedule.id == Appointment.schedule_id)
            .where(
                Appointment.patient_id == patient_id,
                Appointment.status == AppointmentStatus.PLANNED,
                _slot_after(now),
            )
        )
        if active >= MAX_ACTIVE_PER_PATIENT:
            raise ConflictError(
                "too_many_active_appointments",
                f"Нельзя иметь больше {MAX_ACTIVE_PER_PATIENT} активных записей",
            )

    appointment = Appointment(
        patient_id=patient_id, schedule_id=slot.id, service_id=service.id, price=service.price
    )
    session.add(appointment)
    slot.status = SlotStatus.BOOKED
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError("slot_unavailable", "Слот уже занят или закрыт") from None

    return await _detail(session, await _load(session, appointment.id), with_patient=by_admin)


async def cancel(
    session: AsyncSession,
    appointment_id: int,
    *,
    reason: str | None,
    by: CancelInitiator,
    patient_id: int | None = None,
) -> AppointmentDetailOut:
    a = await _load(session, appointment_id, patient_id=patient_id, lock=True)
    _require_status(a, AppointmentStatus.PLANNED)
    if by == CancelInitiator.PATIENT and _slot_start(a.schedule) <= _now():
        raise BadRequestError("too_late", "Приём уже начался — отменить запись нельзя")

    a.status = AppointmentStatus.CANCELED
    a.cancel_reason = (reason or "").strip() or PATIENT_CANCEL_REASON
    a.canceled_at = datetime.now(UTC)
    a.canceled_by = by
    # Запись заблокирована, поэтому слот её параллельно никто не изменит.
    a.schedule.status = SlotStatus.FREE
    await session.commit()
    return await _detail(session, a, with_patient=by == CancelInitiator.ADMINISTRATOR)


async def reschedule(
    session: AsyncSession,
    appointment_id: int,
    new_schedule_id: int,
    *,
    patient_id: int | None = None,
) -> AppointmentDetailOut:
    now = _now()
    a = await _load(session, appointment_id, patient_id=patient_id, lock=True)
    _require_status(a, AppointmentStatus.PLANNED)
    old = await _lock_slot(session, a.schedule_id)
    if _slot_start(old) <= now:
        raise BadRequestError("too_late", "Приём уже начался — перенести запись нельзя")

    new = await _lock_slot(session, new_schedule_id)
    if new.id == old.id:
        raise BadRequestError("same_slot", "Запись уже на этом слоте")
    if new.status != SlotStatus.FREE:
        raise ConflictError("slot_unavailable", "Слот уже занят или закрыт")
    if _slot_start(new) <= now:
        raise BadRequestError("slot_in_past", "Нельзя перенести на прошедшее время")
    same_owner = new.doctor_id == old.doctor_id if old.doctor_id else (
        new.doctor_id is None and new.cabinet == old.cabinet
    )
    if not same_owner:
        raise BadRequestError("different_owner", "Перенести можно только к тому же врачу или в тот же кабинет")
    await _check_patient_free(session, a.patient_id, new, exclude_id=a.id)

    old.status = SlotStatus.FREE
    new.status = SlotStatus.BOOKED
    a.schedule_id = new.id
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError("slot_unavailable", "Слот уже занят или закрыт") from None
    return await _detail(session, await _load(session, a.id), with_patient=patient_id is None)


# ---------- Отметки ----------


async def mark_attended_no_doctor(session: AsyncSession, appointment_id: int) -> AppointmentDetailOut:
    a = await _load(session, appointment_id, lock=True)
    _require_status(a, AppointmentStatus.PLANNED)
    if a.schedule.doctor_id is not None:
        raise BadRequestError("requires_doctor", "Приём у врача отмечает и завершает сам врач")
    if _slot_start(a.schedule) > _now():
        raise BadRequestError("too_early", "Время записи ещё не наступило")

    a.status = AppointmentStatus.COMPLETED
    a.conclusion = NO_DOCTOR_CONCLUSION
    if a.service.category == ServiceCategory.ANALYSIS:
        session.add(
            Analysis(
                patient_id=a.patient_id,
                appointment_id=a.id,
                name=a.service.name,
                analysis_date=a.schedule.work_date,
                status=AnalysisStatus.PROCESSING,
            )
        )
    await session.commit()
    return await _detail(session, a, with_patient=True)


async def mark_no_show(
    session: AsyncSession, appointment_id: int, *, doctor_id: int | None = None
) -> AppointmentDetailOut:
    a = await _load(session, appointment_id, doctor_id=doctor_id, lock=True)
    _require_status(a, AppointmentStatus.PLANNED)
    if _slot_start(a.schedule) > _now():
        raise BadRequestError("too_early", "Время записи ещё не наступило")
    a.status = AppointmentStatus.NO_SHOW
    await session.commit()
    return await _detail(session, a, with_patient=True)


async def start(session: AsyncSession, appointment_id: int, doctor_id: int) -> DoctorAppointmentOut:
    a = await _load(session, appointment_id, doctor_id=doctor_id, lock=True)
    _require_status(a, AppointmentStatus.PLANNED)
    if a.schedule.work_date > _now().date():
        raise BadRequestError("too_early", "Отметить приход можно только в день приёма или позже")
    a.status = AppointmentStatus.IN_PROGRESS
    await session.commit()
    return await _doctor_out(session, a)


async def complete(
    session: AsyncSession, appointment_id: int, doctor_id: int, data: CompleteIn
) -> AppointmentDetailOut:
    a = await _load(session, appointment_id, doctor_id=doctor_id, lock=True)
    _require_status(a, AppointmentStatus.IN_PROGRESS)
    today = _now().date()
    for p in data.prescriptions:
        if p.valid_until is not None and p.valid_until < today:
            raise BadRequestError("invalid_prescription", "Срок действия рецепта не может быть в прошлом")

    a.status = AppointmentStatus.COMPLETED
    a.conclusion = data.conclusion
    session.add_all(
        Prescription(
            appointment_id=a.id,
            prescription_date=today,
            valid_until=p.valid_until,
            medicine=p.medicine.strip(),
            dosage=p.dosage,
            instructions=p.instructions,
        )
        for p in data.prescriptions
    )
    await session.commit()
    return await _detail(session, a, with_patient=True)


# ---------- Списки ----------


async def _page(session: AsyncSession, conditions: list, order, limit: int, offset: int, with_patient: bool) -> AppointmentPage:
    base = select(Appointment).join(Schedule, Schedule.id == Appointment.schedule_id).where(*conditions)
    total = await session.scalar(select(func.count()).select_from(base.subquery()))
    rows = await session.scalars(base.options(*_FULL_LOAD).order_by(*order).limit(limit).offset(offset))
    return AppointmentPage(items=[AppointmentOut(**_to_out(a, with_patient)) for a in rows], total=total or 0)


async def patient_list(
    session: AsyncSession, patient_id: int, scope: Literal["upcoming", "past"], limit: int, offset: int
) -> AppointmentPage:
    upcoming = and_(
        _slot_after(_now()),
        Appointment.status.in_([AppointmentStatus.PLANNED, AppointmentStatus.IN_PROGRESS]),
    )
    if scope == "upcoming":
        return await _page(
            session, [Appointment.patient_id == patient_id, upcoming],
            [Schedule.work_date, Schedule.start_time], limit, offset, with_patient=False,
        )
    return await _page(
        session, [Appointment.patient_id == patient_id, ~upcoming],
        [Schedule.work_date.desc(), Schedule.start_time.desc()], limit, offset, with_patient=False,
    )


async def patient_detail(session: AsyncSession, patient_id: int, appointment_id: int) -> AppointmentDetailOut:
    return await _detail(session, await _load(session, appointment_id, patient_id=patient_id), with_patient=False)


async def admin_list(
    session: AsyncSession,
    limit: int,
    offset: int,
    *,
    on_date: date | None,
    date_from: date | None,
    date_to: date | None,
    doctor_id: int | None,
    cabinet: str | None,
    patient_id: int | None,
    status: AppointmentStatus | None,
) -> AppointmentPage:
    conditions = []
    if on_date is not None:
        conditions.append(Schedule.work_date == on_date)
    if date_from is not None:
        conditions.append(Schedule.work_date >= date_from)
    if date_to is not None:
        conditions.append(Schedule.work_date <= date_to)
    if doctor_id is not None:
        conditions.append(Schedule.doctor_id == doctor_id)
    if cabinet is not None:
        conditions.append(Schedule.cabinet == cabinet)
    if patient_id is not None:
        conditions.append(Appointment.patient_id == patient_id)
    if status is not None:
        conditions.append(Appointment.status == status)
    return await _page(
        session, conditions, [Schedule.work_date.desc(), Schedule.start_time, Schedule.cabinet],
        limit, offset, with_patient=True,
    )


async def admin_detail(session: AsyncSession, appointment_id: int) -> AppointmentDetailOut:
    return await _detail(session, await _load(session, appointment_id), with_patient=True)


async def doctor_day(session: AsyncSession, doctor_id: int, on_date: date | None) -> list[DoctorAppointmentOut]:
    rows = await session.scalars(
        select(Appointment)
        .join(Schedule, Schedule.id == Appointment.schedule_id)
        .where(
            Schedule.doctor_id == doctor_id,
            Schedule.work_date == (on_date or _now().date()),
            Appointment.status != AppointmentStatus.CANCELED,
        )
        .options(*_FULL_LOAD)
        .order_by(Schedule.start_time)
    )
    return [await _doctor_out(session, a) for a in rows]


async def doctor_month(session: AsyncSession, doctor_id: int, month: str) -> list[DayLoadOut]:
    try:
        first = datetime.strptime(month, "%Y-%m").date()
    except ValueError:
        raise BadRequestError("invalid_month", "Месяц указывается в формате ГГГГ-ММ") from None
    next_month = (first + timedelta(days=32)).replace(day=1)
    rows = await session.execute(
        select(Schedule.work_date, func.count())
        .select_from(Appointment)
        .join(Schedule, Schedule.id == Appointment.schedule_id)
        .where(
            Schedule.doctor_id == doctor_id,
            Schedule.work_date >= first,
            Schedule.work_date < next_month,
            Appointment.status != AppointmentStatus.CANCELED,
        )
        .group_by(Schedule.work_date)
        .order_by(Schedule.work_date)
    )
    return [DayLoadOut(work_date=d, appointments=n) for d, n in rows]


async def doctor_detail(session: AsyncSession, doctor_id: int, appointment_id: int) -> DoctorAppointmentOut:
    return await _doctor_out(session, await _load(session, appointment_id, doctor_id=doctor_id))
