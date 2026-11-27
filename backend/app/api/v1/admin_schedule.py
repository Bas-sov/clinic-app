from datetime import date

from fastapi import APIRouter, Depends, status

from app.api.deps import PaginationDep, SessionDep, require_role
from app.models import SlotStatus
from app.schemas.schedule import AdminSlotOut, AdminSlotPage, ScheduleBatchIn, ScheduleBatchOut, SlotStatusIn
from app.services import schedule

router = APIRouter(prefix="/admin/schedule", tags=["Админ: расписание"], dependencies=[Depends(require_role("admin"))])


@router.post("/batch", response_model=ScheduleBatchOut, status_code=status.HTTP_201_CREATED)
async def create_batch(data: ScheduleBatchIn, session: SessionDep) -> ScheduleBatchOut:
    return await schedule.create_batch(session, data)


@router.get("", response_model=AdminSlotPage)
async def list_slots(
    session: SessionDep,
    pagination: PaginationDep,
    doctor_id: int | None = None,
    cabinet: str | None = None,
    slot_status: SlotStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> AdminSlotPage:
    return await schedule.list_slots(
        session, pagination.limit, pagination.offset, doctor_id, cabinet, slot_status, date_from, date_to
    )


@router.patch("/{slot_id}", response_model=AdminSlotOut)
async def set_slot_status(slot_id: int, data: SlotStatusIn, session: SessionDep) -> AdminSlotOut:
    return await schedule.set_slot_status(session, slot_id, data.status)


@router.delete("/{slot_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_slot(slot_id: int, session: SessionDep) -> None:
    await schedule.delete_slot(session, slot_id)
