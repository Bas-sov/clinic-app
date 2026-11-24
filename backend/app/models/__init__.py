# Импорт всех моделей в одном месте: SQLAlchemy должен знать о каждой,
# чтобы связи вида relationship("Patient") нашли свой класс.
from app.models.administrator import Administrator
from app.models.analysis import Analysis
from app.models.appointment import Appointment
from app.models.certificate import Certificate
from app.models.doctor import Doctor
from app.models.enums import (
    AnalysisStatus,
    AppointmentStatus,
    CancelInitiator,
    ServiceCategory,
    SlotStatus,
)
from app.models.login_code import LoginCode
from app.models.patient import Patient
from app.models.prescription import Prescription
from app.models.schedule import Schedule
from app.models.service import Service
from app.models.sick_leave import SickLeave
from app.models.specialty import Specialty

__all__ = [
    "Administrator",
    "Analysis",
    "AnalysisStatus",
    "Appointment",
    "AppointmentStatus",
    "CancelInitiator",
    "Certificate",
    "Doctor",
    "LoginCode",
    "Patient",
    "Prescription",
    "Schedule",
    "Service",
    "ServiceCategory",
    "SickLeave",
    "SlotStatus",
    "Specialty",
]
