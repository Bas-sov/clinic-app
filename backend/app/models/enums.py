from enum import StrEnum

from sqlalchemy.dialects.postgresql import ENUM


class SlotStatus(StrEnum):
    FREE = "free"
    BOOKED = "booked"
    UNAVAILABLE = "unavailable"


class AppointmentStatus(StrEnum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    CANCELED = "canceled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class CancelInitiator(StrEnum):
    PATIENT = "patient"
    ADMINISTRATOR = "administrator"


class ServiceCategory(StrEnum):
    CONSULTATION = "consultation"
    ANALYSIS = "analysis"
    PROCEDURE = "procedure"


class AnalysisStatus(StrEnum):
    PROCESSING = "processing"
    READY = "ready"


def _pg_enum(enum_cls: type[StrEnum], name: str) -> ENUM:
    # Типы уже созданы в schema.sql (create_type=False).
    # values_callable: в БД пишем значения ("free"), а не имена членов ("FREE").
    return ENUM(
        enum_cls,
        name=name,
        create_type=False,
        values_callable=lambda members: [m.value for m in members],
    )


slot_status_type = _pg_enum(SlotStatus, "slot_status")
appointment_status_type = _pg_enum(AppointmentStatus, "appointment_status")
cancel_initiator_type = _pg_enum(CancelInitiator, "cancel_initiator")
service_category_type = _pg_enum(ServiceCategory, "service_category")
analysis_status_type = _pg_enum(AnalysisStatus, "analysis_status")
