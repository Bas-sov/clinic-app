import logging
import time
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.contacts import normalize_contact
from app.core.errors import ConflictError, TooManyRequestsError, UnauthorizedError
from app.core.security import (
    InvalidTokenError,
    Role,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_login_code,
    hash_login_code,
    hash_password,
    verify_login_code,
    verify_password,
)
from app.models import Administrator, Doctor, LoginCode, Patient
from app.schemas.auth import (
    MeOut,
    RegisterIn,
    RegistrationRequiredOut,
    StaffLoginIn,
    TokenPairOut,
)

logger = logging.getLogger(__name__)

User = Patient | Doctor | Administrator
MODEL_BY_ROLE: dict[Role, type[User]] = {"patient": Patient, "doctor": Doctor, "admin": Administrator}

CODE_RESEND_SECONDS = 60
STAFF_MAX_FAILS = 5
STAFF_LOCK_SECONDS = 15 * 60

# Хеш-пустышка: проверяем его, когда email не найден, чтобы ответ шёл столько же,
# сколько при неверном пароле, и по времени нельзя было понять, есть ли такой email.
_DUMMY_HASH = hash_password("dummy-password-for-timing")

# email -> (число неудач подряд, момент окончания блокировки). Живёт до перезапуска сервера.
_staff_fails: dict[str, tuple[int, float]] = {}


def _tokens(user_id: int, role: Role) -> TokenPairOut:
    return TokenPairOut(
        access_token=create_access_token(user_id, role),
        refresh_token=create_refresh_token(user_id, role),
    )


async def load_active_user(session: AsyncSession, role: Role, user_id: int) -> User:
    user = await session.get(MODEL_BY_ROLE[role], user_id)
    if user is None:
        raise UnauthorizedError("user_not_found", "Пользователь не найден")
    if getattr(user, "is_active", True) is False:
        raise UnauthorizedError("account_disabled", "Учётная запись отключена")
    return user


async def _find_patient(session: AsyncSession, contact: str) -> Patient | None:
    kind, value = normalize_contact(contact)
    column = Patient.phone if kind == "phone" else Patient.email
    return await session.scalar(select(Patient).where(column == value))


async def request_code(session: AsyncSession, contact: str) -> None:
    now = datetime.now(UTC)
    last = await session.scalar(
        select(LoginCode).where(LoginCode.contact == contact).order_by(LoginCode.created_at.desc()).limit(1)
    )
    if last is not None:
        wait = CODE_RESEND_SECONDS - int((now - last.created_at).total_seconds())
        if wait > 0:
            raise TooManyRequestsError("code_resend_too_early", f"Повторно запросить код можно через {wait} с")

    code = generate_login_code()
    ttl = timedelta(minutes=get_settings().login_code_ttl_minutes)
    session.add(LoginCode(contact=contact, code_hash=hash_login_code(code), expires_at=now + ttl))
    await session.commit()
    # Заглушка вместо SMS/email до подключения реальной отправки.
    logger.info("Код входа для %s: %s", contact, code)


async def _check_code(session: AsyncSession, contact: str, code: str) -> LoginCode:
    """Проверяет последний код для контакта. Неверная попытка сохраняется сразу."""
    now = datetime.now(UTC)
    login_code = await session.scalar(
        select(LoginCode)
        .where(LoginCode.contact == contact)
        .order_by(LoginCode.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if login_code is None or login_code.used_at is not None or login_code.expires_at <= now:
        raise UnauthorizedError("code_expired", "Код недействителен или истёк, запросите новый")

    max_attempts = get_settings().login_code_max_attempts
    if login_code.attempts >= max_attempts:
        raise TooManyRequestsError("code_attempts_exceeded", "Попытки исчерпаны, запросите новый код")

    if not verify_login_code(code, login_code.code_hash):
        login_code.attempts += 1
        left = max_attempts - login_code.attempts
        await session.commit()
        if left == 0:
            raise TooManyRequestsError("code_attempts_exceeded", "Попытки исчерпаны, запросите новый код")
        raise UnauthorizedError("code_invalid", f"Неверный код, осталось попыток: {left}")
    return login_code


async def verify_code(session: AsyncSession, contact: str, code: str) -> TokenPairOut | RegistrationRequiredOut:
    login_code = await _check_code(session, contact, code)
    patient = await _find_patient(session, contact)
    if patient is None:
        # Код не тратим: он понадобится ещё раз вместе с анкетой.
        await session.commit()
        return RegistrationRequiredOut()

    login_code.used_at = datetime.now(UTC)
    await session.commit()
    return _tokens(patient.id, "patient")


async def register(session: AsyncSession, data: RegisterIn) -> TokenPairOut:
    login_code = await _check_code(session, data.contact, data.code)
    login_code.used_at = datetime.now(UTC)

    patient = await _find_patient(session, data.contact)
    if patient is None:
        kind, value = normalize_contact(data.contact)
        patient = Patient(
            last_name=data.last_name,
            first_name=data.first_name,
            middle_name=data.middle_name,
            birth_date=data.birth_date,
            phone=value if kind == "phone" else None,
            email=value if kind == "email" else None,
        )
        session.add(patient)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise ConflictError("patient_already_exists", "Пациент с таким контактом уже зарегистрирован") from None
    return _tokens(patient.id, "patient")


def _check_staff_lock(email: str) -> None:
    fails, locked_until = _staff_fails.get(email, (0, 0.0))
    left = int(locked_until - time.monotonic())
    if left > 0:
        raise TooManyRequestsError(
            "too_many_login_attempts", f"Слишком много попыток, попробуйте через {left // 60 + 1} мин"
        )


def _register_staff_fail(email: str) -> None:
    fails, _ = _staff_fails.get(email, (0, 0.0))
    fails += 1
    locked_until = time.monotonic() + STAFF_LOCK_SECONDS if fails >= STAFF_MAX_FAILS else 0.0
    _staff_fails[email] = (0 if locked_until else fails, locked_until)


async def staff_login(session: AsyncSession, data: StaffLoginIn, role: Role) -> TokenPairOut:
    _check_staff_lock(data.email)
    model = MODEL_BY_ROLE[role]
    user = await session.scalar(select(model).where(model.email == data.email))

    if user is None:
        verify_password(data.password, _DUMMY_HASH)
        _register_staff_fail(data.email)
        raise UnauthorizedError("invalid_credentials", "Неверный email или пароль")
    if not verify_password(data.password, user.password_hash):
        _register_staff_fail(data.email)
        raise UnauthorizedError("invalid_credentials", "Неверный email или пароль")

    _staff_fails.pop(data.email, None)
    if not user.is_active:
        raise UnauthorizedError("account_disabled", "Учётная запись отключена")
    return _tokens(user.id, role)


async def refresh(session: AsyncSession, refresh_token: str) -> TokenPairOut:
    try:
        payload = decode_token(refresh_token, "refresh")
    except InvalidTokenError:
        raise UnauthorizedError("invalid_token", "Сессия истекла, войдите заново") from None
    await load_active_user(session, payload.role, payload.user_id)
    return _tokens(payload.user_id, payload.role)


async def me(session: AsyncSession, role: Role, user: User) -> MeOut:
    data = MeOut(
        role=role,
        id=user.id,
        last_name=user.last_name,
        first_name=user.first_name,
        middle_name=getattr(user, "middle_name", None),
        phone=user.phone,
        email=user.email,
    )
    if isinstance(user, Patient):
        data.birth_date = user.birth_date
    if isinstance(user, Doctor):
        await session.refresh(user, ["specialty"])
        data.specialty = user.specialty.name
    return data
