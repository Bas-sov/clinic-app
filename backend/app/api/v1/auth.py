from fastapi import APIRouter, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.auth import (
    MeOut,
    RefreshIn,
    RegisterIn,
    RegistrationRequiredOut,
    RequestCodeIn,
    StaffLoginIn,
    TokenPairOut,
    VerifyCodeIn,
)
from app.services import auth

router = APIRouter(tags=["Вход"])


@router.post("/auth/patient/request-code", status_code=status.HTTP_204_NO_CONTENT)
async def request_code(data: RequestCodeIn, session: SessionDep) -> None:
    await auth.request_code(session, data.contact)


@router.post("/auth/patient/verify-code", response_model=TokenPairOut | RegistrationRequiredOut)
async def verify_code(data: VerifyCodeIn, session: SessionDep) -> TokenPairOut | RegistrationRequiredOut:
    return await auth.verify_code(session, data.contact, data.code)


@router.post("/auth/patient/register", response_model=TokenPairOut)
async def register(data: RegisterIn, session: SessionDep) -> TokenPairOut:
    return await auth.register(session, data)


@router.post("/auth/doctor/login", response_model=TokenPairOut)
async def doctor_login(data: StaffLoginIn, session: SessionDep) -> TokenPairOut:
    return await auth.staff_login(session, data, "doctor")


@router.post("/auth/admin/login", response_model=TokenPairOut)
async def admin_login(data: StaffLoginIn, session: SessionDep) -> TokenPairOut:
    return await auth.staff_login(session, data, "admin")


@router.post("/auth/refresh", response_model=TokenPairOut)
async def refresh(data: RefreshIn, session: SessionDep) -> TokenPairOut:
    return await auth.refresh(session, data.refresh_token)


@router.get("/me", response_model=MeOut)
async def me(current: CurrentUser, session: SessionDep) -> MeOut:
    return await auth.me(session, current.role, current.user)
