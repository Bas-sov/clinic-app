import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, get_args

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import get_settings

Role = Literal["patient", "doctor", "admin"]
TokenType = Literal["access", "refresh"]

LOGIN_CODE_LENGTH = 6
JWT_ALGORITHM = "HS256"

_hasher = PasswordHasher()


class InvalidTokenError(Exception):
    """Токен поддельный, просрочен или не того типа."""


@dataclass(frozen=True)
class TokenPayload:
    user_id: int
    role: Role


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def generate_login_code() -> str:
    return "".join(secrets.choice("0123456789") for _ in range(LOGIN_CODE_LENGTH))


def hash_login_code(code: str) -> str:
    return _hasher.hash(code)


def verify_login_code(code: str, code_hash: str) -> bool:
    return verify_password(code, code_hash)


def _create_token(user_id: int, role: Role, token_type: TokenType, lifetime: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + lifetime,
    }
    return jwt.encode(payload, get_settings().jwt_secret, algorithm=JWT_ALGORITHM)


def create_access_token(user_id: int, role: Role) -> str:
    minutes = get_settings().jwt_access_ttl_minutes
    return _create_token(user_id, role, "access", timedelta(minutes=minutes))


def create_refresh_token(user_id: int, role: Role) -> str:
    days = get_settings().jwt_refresh_ttl_days
    return _create_token(user_id, role, "refresh", timedelta(days=days))


def decode_token(token: str, expected_type: TokenType) -> TokenPayload:
    try:
        payload = jwt.decode(
            token,
            get_settings().jwt_secret,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "role", "type"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError from exc

    if payload["type"] != expected_type or payload["role"] not in get_args(Role):
        raise InvalidTokenError
    return TokenPayload(user_id=int(payload["sub"]), role=payload["role"])
