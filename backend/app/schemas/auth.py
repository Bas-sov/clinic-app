from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.core.contacts import normalize_contact, normalize_email
from app.core.security import LOGIN_CODE_LENGTH, Role


class RequestCodeIn(BaseModel):
    contact: str = Field(max_length=255)

    @field_validator("contact")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_contact(value)[1]


class VerifyCodeIn(RequestCodeIn):
    code: str = Field(pattern=rf"^\d{{{LOGIN_CODE_LENGTH}}}$")


class RegisterIn(VerifyCodeIn):
    last_name: str = Field(min_length=1, max_length=100)
    first_name: str = Field(min_length=1, max_length=100)
    middle_name: str | None = Field(default=None, max_length=100)
    birth_date: date

    @field_validator("last_name", "first_name")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Поле не может быть пустым")
        return value

    @field_validator("middle_name")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        return (value or "").strip() or None

    @field_validator("birth_date")
    @classmethod
    def _check_birth_date(cls, value: date) -> date:
        if value > date.today() or value.year < 1900:
            raise ValueError("Неверная дата рождения")
        return value


class StaffLoginIn(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return normalize_email(value)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"


class RegistrationRequiredOut(BaseModel):
    registration_required: Literal[True] = True


class MeOut(BaseModel):
    role: Role
    id: int
    last_name: str
    first_name: str
    middle_name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: date | None = None
    specialty: str | None = None
