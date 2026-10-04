"""Application users and roles."""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from database.session import Base

ROLES = ("admin", "doctor", "staff_coordinator")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(120), unique=True)
    hashed_password: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32))  # admin | doctor | staff_coordinator
    doctor_id: Mapped[str | None] = mapped_column(String(16), nullable=True)  # links a doctor user to a Doctor row
