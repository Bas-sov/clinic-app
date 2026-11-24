from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Identity, Integer, Numeric, String, Text, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ServiceCategory, service_category_type

if TYPE_CHECKING:
    from app.models.specialty import Specialty


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Identity(always=True), primary_key=True)
    specialty_id: Mapped[int | None] = mapped_column(ForeignKey("specialties.id"))
    category: Mapped[ServiceCategory] = mapped_column(service_category_type)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    preparation: Mapped[str | None] = mapped_column(Text)
    is_visible: Mapped[bool] = mapped_column(Boolean, server_default=true())

    specialty: Mapped["Specialty | None"] = relationship(lazy="raise")
