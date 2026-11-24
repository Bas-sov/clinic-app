from datetime import datetime

from sqlalchemy import DateTime, Identity, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class LoginCode(Base):
    __tablename__ = "login_codes"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    contact: Mapped[str] = mapped_column(String(255))
    code_hash: Mapped[str] = mapped_column(String(255))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
