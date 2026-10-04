"""Agent recommendations: an auditable record that administrators can accept or override."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database.session import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    agent: Mapped[str] = mapped_column(String(32), index=True)  # scheduling | resource | staff | emergency | analytics
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending | accepted | overridden
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)
    decided_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    override_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
