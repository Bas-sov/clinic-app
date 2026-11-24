from sqlalchemy import Boolean, Identity, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Administrator(Base):
    __tablename__ = "administrators"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20), unique=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=true())
