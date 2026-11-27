from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import SlotStatus

MAX_BATCH_DAYS = 92


class ScheduleBatchIn(BaseModel):
    doctor_id: int | None = None
    cabinet: str | None = Field(default=None, min_length=1, max_length=20)
    date_from: date
    date_to: date
    weekdays: list[int] = Field(min_length=1, max_length=7, description="1 = пн … 7 = вс")
    start_time: time
    end_time: time
    slot_minutes: int = Field(ge=5, le=240)

    @model_validator(mode="after")
    def _check(self) -> "ScheduleBatchIn":
        if self.date_to < self.date_from:
            raise ValueError("Дата окончания раньше даты начала")
        if (self.date_to - self.date_from).days > MAX_BATCH_DAYS:
            raise ValueError("Период не может быть длиннее 3 месяцев")
        if self.end_time <= self.start_time:
            raise ValueError("Время окончания должно быть позже времени начала")
        if any(d < 1 or d > 7 for d in self.weekdays):
            raise ValueError("Дни недели задаются числами от 1 (пн) до 7 (вс)")
        if self.doctor_id is None and self.cabinet is None:
            raise ValueError("Для слотов без врача укажите кабинет")
        self.weekdays = sorted(set(self.weekdays))
        return self


class ScheduleBatchOut(BaseModel):
    created: int
    skipped: int


class AdminSlotOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int | None
    cabinet: str
    work_date: date
    start_time: time
    end_time: time
    status: SlotStatus


class AdminSlotPage(BaseModel):
    items: list[AdminSlotOut]
    total: int


class SlotStatusIn(BaseModel):
    status: Literal["free", "unavailable"]
