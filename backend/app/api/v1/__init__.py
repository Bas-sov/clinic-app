from fastapi import APIRouter

from app.api.v1 import admin_schedule, auth

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(admin_schedule.router)
