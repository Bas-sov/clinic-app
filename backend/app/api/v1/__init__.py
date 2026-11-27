from fastapi import APIRouter

from app.api.v1 import admin_appointments, admin_schedule, auth, doctor_appointments, patient_appointments

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(patient_appointments.router)
api_router.include_router(doctor_appointments.router)
api_router.include_router(admin_appointments.router)
api_router.include_router(admin_schedule.router)
