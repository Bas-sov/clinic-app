"""Создание первого администратора.

Запуск из папки backend:  python -m app.scripts.create_admin
"""

import asyncio
import sys
from getpass import getpass

from sqlalchemy import or_, select

from app.core.contacts import normalize_email, normalize_phone
from app.core.security import PASSWORD_MIN_LENGTH, hash_password
from app.db.session import SessionLocal, engine
from app.models import Administrator


def _ask(prompt: str, normalize=None, max_length: int = 100) -> str:
    while True:
        value = input(prompt).strip()
        if not value:
            print("  Поле не может быть пустым")
            continue
        if len(value) > max_length:
            print(f"  Не длиннее {max_length} символов")
            continue
        if normalize is None:
            return value
        try:
            return normalize(value)
        except ValueError as exc:
            print(f"  {exc}")


def _ask_password() -> str:
    while True:
        password = getpass("Пароль: ")
        if len(password) < PASSWORD_MIN_LENGTH:
            print(f"  Пароль должен быть не короче {PASSWORD_MIN_LENGTH} символов")
            continue
        if getpass("Повторите пароль: ") != password:
            print("  Пароли не совпадают")
            continue
        return password


async def _create(last_name: str, first_name: str, phone: str, email: str, password: str) -> int | None:
    async with SessionLocal() as session:
        exists = await session.scalar(
            select(Administrator.id).where(or_(Administrator.email == email, Administrator.phone == phone))
        )
        if exists is not None:
            return None
        admin = Administrator(
            last_name=last_name,
            first_name=first_name,
            phone=phone,
            email=email,
            password_hash=hash_password(password),
        )
        session.add(admin)
        await session.commit()
        return admin.id


async def main() -> int:
    print("Создание администратора «Эконом Клиники»\n")
    last_name = _ask("Фамилия: ")
    first_name = _ask("Имя: ")
    phone = _ask("Телефон: ", normalize_phone, max_length=20)
    email = _ask("Email: ", normalize_email, max_length=255)
    password = _ask_password()
    try:
        admin_id = await _create(last_name, first_name, phone, email, password)
    finally:
        await engine.dispose()

    if admin_id is None:
        print("\n❌ Администратор с таким email или телефоном уже существует")
        return 1
    print(f"\n✅ Администратор создан (id = {admin_id}). Вход: {email}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
