from datetime import date, datetime, time, timedelta

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import BadRequestError, ConflictError, NotFoundError
from app.models import Appointment, Doctor, Schedule, SlotStatus
from app.schemas.schedule import AdminSlotOut, AdminSlotPage, ScheduleBatchIn, ScheduleBatchOut

DEFAULT_LIST_DAYS = 14


def _now() -> datetime:
    return datetime.now(get_settings().clinic_tz).replace(tzinfo=None)


def _ensure_not_past(slot: Schedule) -> None:
    if datetime.combine(slot.work_date, slot.start_time) <= _now():
        raise BadRequestError("slot_in_past", "Нельзя изменять прошедшие слоты")


async def _get_slot(session: AsyncSession, slot_id: int) -> Schedule:
    slot = await session.get(Schedule, slot_id, with_for_update=True)
    if slot is None:
        raise NotFoundError("slot_not_found", "Слот не найден")
    return slot


def _candidates(data: ScheduleBatchIn) -> list[tuple[date, time, time]]:
    step = timedelta(minutes=data.slot_minutes)
    result = []
    day = data.date_from
    while day <= data.date_to:
        if day.isoweekday() in data.weekdays:
            start = datetime.combine(day, data.start_time)
            end_limit = datetime.combine(day, data.end_time)
            # Неполный «хвост» в конце интервала не создаём.
            while start + step <= end_limit:
                result.append((day, start.time(), (start + step).time()))
                start += step
        day += timedelta(days=1)
    return result


async def create_batch(session: AsyncSession, data: ScheduleBatchIn) -> ScheduleBatchOut:
    now = _now()
    if data.date_from < now.date():
        raise BadRequestError("date_in_past", "Нельзя создавать слоты в прошедших датах")

    cabinet = data.cabinet
    if data.doctor_id is not None:
        doctor = await session.get(Doctor, data.doctor_id)
        if doctor is None:
            raise NotFoundError("doctor_not_found", "Врач не найден")
        if not doctor.is_active:
            raise BadRequestError("doctor_inactive", "Врач отключён, создавать ему слоты нельзя")
        cabinet = cabinet or doctor.cabinet
        if cabinet is None:
            raise BadRequestError("cabinet_required", "У врача не указан кабинет — передайте его явно")

    owner = [Schedule.cabinet == cabinet]
    if data.doctor_id is not None:
        owner.append(Schedule.doctor_id == data.doctor_id)
    existing = (
        await session.execute(
            select(Schedule.work_date, Schedule.start_time, Schedule.end_time).where(
                Schedule.work_date.between(data.date_from, data.date_to), or_(*owner)
            )
        )
    ).all()
    busy: dict[date, list[tuple[time, time]]] = {}
    for work_date, start, end in existing:
        busy.setdefault(work_date, []).append((start, end))

    created, skipped = [], 0
    for day, start, end in _candidates(data):
        overlaps = any(start < b_end and end > b_start for b_start, b_end in busy.get(day, []))
        if overlaps or datetime.combine(day, start) <= now:
            skipped += 1
            continue
        created.append(
            Schedule(doctor_id=data.doctor_id, cabinet=cabinet, work_date=day, start_time=start, end_time=end)
        )

    session.add_all(created)
    try:
        await session.commit()
    except IntegrityError:
        # Кто-то параллельно создал пересекающиеся слоты — пакет целиком откатывается.
        await session.rollback()
        raise ConflictError("schedule_conflict", "Расписание изменилось, повторите создание") from None
    return ScheduleBatchOut(created=len(created), skipped=skipped)


async def list_slots(
    session: AsyncSession,
    limit: int,
    offset: int,
    doctor_id: int | None,
    cabinet: str | None,
    status: SlotStatus | None,
    date_from: date | None,
    date_to: date | None,
) -> AdminSlotPage:
    start = date_from or _now().date()
    end = date_to or start + timedelta(days=DEFAULT_LIST_DAYS)
    conditions = [Schedule.work_date.between(start, end)]
    if doctor_id is not None:
        conditions.append(Schedule.doctor_id == doctor_id)
    if cabinet is not None:
        conditions.append(Schedule.cabinet == cabinet)
    if status is not None:
        conditions.append(Schedule.status == status)

    total = await session.scalar(select(func.count()).select_from(Schedule).where(*conditions))
    rows = await session.scalars(
        select(Schedule)
        .where(*conditions)
        .order_by(Schedule.work_date, Schedule.start_time, Schedule.cabinet)
        .limit(limit)
        .offset(offset)
    )
    return AdminSlotPage(items=[AdminSlotOut.model_validate(r) for r in rows], total=total or 0)


async def set_slot_status(session: AsyncSession, slot_id: int, status: str) -> AdminSlotOut:
    slot = await _get_slot(session, slot_id)
    _ensure_not_past(slot)
    if slot.status == SlotStatus.BOOKED:
        raise ConflictError("slot_booked", "На слот есть запись — сначала отмените или перенесите её")
    slot.status = SlotStatus(status)
    await session.commit()
    return AdminSlotOut.model_validate(slot)


async def delete_slot(session: AsyncSession, slot_id: int) -> None:
    slot = await _get_slot(session, slot_id)
    _ensure_not_past(slot)
    if slot.status == SlotStatus.BOOKED:
        raise ConflictError("slot_booked", "На слот есть запись — сначала отмените или перенесите её")
    has_history = await session.scalar(select(exists().where(Appointment.schedule_id == slot.id)))
    if has_history:
        raise ConflictError("slot_has_history", "На слот были записи — его можно только закрыть")
    await session.delete(slot)
    await session.commit()
