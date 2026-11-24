from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Identity, SmallInteger, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.specialty import Specialty


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    middle_name: Mapped[str | None] = mapped_column(String(100))
    specialty_id: Mapped[int] = mapped_column(ForeignKey("specialties.id"))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    experience_years: Mapped[int | None] = mapped_column(SmallInteger)
    cabinet: Mapped[str | None] = mapped_column(String(20))
    education: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())

    specialty: Mapped["Specialty"] = relationship(lazy="raise")
