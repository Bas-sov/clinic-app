from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import InvalidTokenError, Role, TokenPayload, decode_token
from app.db.session import get_session
from app.models import Administrator, Doctor, Patient
from app.services.auth import User, load_active_user

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# auto_error=False: отсутствие токена обрабатываем сами, чтобы ответ был в нашем формате.
_bearer = HTTPBearer(auto_error=False)


async def get_token_payload(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenPayload:
    if credentials is None:
        raise UnauthorizedError("not_authenticated", "Требуется вход в систему")
    try:
        return decode_token(credentials.credentials, "access")
    except InvalidTokenError:
        raise UnauthorizedError("invalid_token", "Сессия истекла, войдите заново") from None


TokenDep = Annotated[TokenPayload, Depends(get_token_payload)]


async def _load_user(session: AsyncSession, payload: TokenPayload) -> User:
    return await load_active_user(session, payload.role, payload.user_id)


def _require_role(role: Role) -> Callable[..., Awaitable[User]]:
    async def dependency(session: SessionDep, payload: TokenDep) -> User:
        if payload.role != role:
            raise ForbiddenError("forbidden_role", "Недостаточно прав")
        return await _load_user(session, payload)

    return dependency


CurrentPatient = Annotated[Patient, Depends(_require_role("patient"))]
CurrentDoctor = Annotated[Doctor, Depends(_require_role("doctor"))]
CurrentAdmin = Annotated[Administrator, Depends(_require_role("admin"))]


@dataclass(frozen=True)
class AuthenticatedUser:
    role: Role
    user: User


async def get_current_user(session: SessionDep, payload: TokenDep) -> AuthenticatedUser:
    return AuthenticatedUser(role=payload.role, user=await _load_user(session, payload))


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


@dataclass(frozen=True)
class Pagination:
    limit: int
    offset: int


def get_pagination(
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(get_pagination)]
