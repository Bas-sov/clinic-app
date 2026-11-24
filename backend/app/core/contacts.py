import re
from typing import Literal

ContactKind = Literal["phone", "email"]

# Те же правила, что CHECK-ограничения в schema.sql.
PHONE_RE = re.compile(r"^\+[0-9]{10,15}$")
EMAIL_RE = re.compile(r"^[a-z0-9._%+-]+@([a-z0-9-]+\.)+[a-z]{2,}$")


def normalize_phone(raw: str) -> str:
    digits = re.sub(r"[\s()\-]", "", raw.strip())
    # Российские номера часто вводят как 8XXXXXXXXXX или 7XXXXXXXXXX.
    if re.fullmatch(r"8\d{10}", digits):
        digits = "+7" + digits[1:]
    elif re.fullmatch(r"7\d{10}", digits):
        digits = "+" + digits
    if not PHONE_RE.match(digits):
        raise ValueError("Неверный формат телефона")
    return digits


def normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if not EMAIL_RE.match(email):
        raise ValueError("Неверный формат email")
    return email


def normalize_contact(raw: str) -> tuple[ContactKind, str]:
    if "@" in raw:
        return "email", normalize_email(raw)
    return "phone", normalize_phone(raw)
