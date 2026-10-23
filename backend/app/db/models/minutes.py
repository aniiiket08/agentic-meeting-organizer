import enum
from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, Enum as PyEnum, ForeignKey, JSON, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MinutesStatus(str, enum.Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"


class Transcript(Base):
    __tablename__ = "transcripts"

    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), unique=True, nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    redacted_text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    meeting = relationship("Meeting")


class Minutes(Base):
    __tablename__ = "minutes"

    meeting_id: Mapped[int] = mapped_column(ForeignKey("meetings.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_discussion_points: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    action_items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[MinutesStatus] = mapped_column(
        PyEnum(MinutesStatus, native_enum=False, values_callable=lambda x: [e.value for e in x]),
        default=MinutesStatus.DRAFT,
        nullable=False,
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    meeting = relationship("Meeting")
    approved_by = relationship("User")
