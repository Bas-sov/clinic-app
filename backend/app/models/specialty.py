from sqlalchemy import Identity, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Specialty(Base):
    __tablename__ = "specialties"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
