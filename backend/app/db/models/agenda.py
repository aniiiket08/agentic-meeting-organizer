import enum
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Enum as PyEnum, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AgendaStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Agenda(Base):
    __tablename__ = "agendas"

    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), unique=True, nullable=False)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[AgendaStatus] = mapped_column(
        PyEnum(AgendaStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=AgendaStatus.DRAFT,
        nullable=False,
    )
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meeting = relationship("Meeting")
    approved_by = relationship("User")


class Decision(Base):
    __tablename__ = "decisions"

    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[str | None] = mapped_column(String(50), nullable=True)

    meeting = relationship("Meeting")
