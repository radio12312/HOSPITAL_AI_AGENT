"""Beds, staff and equipment."""

from __future__ import annotations

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base
from models.clinical import Patient


class Bed(Base):
    __tablename__ = "beds"

    id: Mapped[int] = mapped_column(primary_key=True)
    bed_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    ward: Mapped[str] = mapped_column(String(40), index=True)
    bed_type: Mapped[str] = mapped_column(String(16))  # icu | general | cardiac | pediatric | surgical | emergency
    occupancy_status: Mapped[str] = mapped_column(String(16), index=True)  # available | occupied | reserved | maintenance
    patient_id: Mapped[str | None] = mapped_column(ForeignKey("patients.patient_id"), nullable=True, index=True)

    patient: Mapped[Patient | None] = relationship(lazy="joined")


class Staff(Base):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(primary_key=True)
    staff_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    role: Mapped[str] = mapped_column(String(40))  # Nurse | Senior Nurse | Technician | Surgeon | Paramedic | ...
    department: Mapped[str] = mapped_column(String(40), index=True)
    shift: Mapped[str] = mapped_column(String(16))  # morning | evening | night
    workload_score: Mapped[float] = mapped_column(Float)  # 0 - 100
    on_duty: Mapped[bool] = mapped_column(Boolean, default=True)


class Equipment(Base):
    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    equipment_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    availability_status: Mapped[str] = mapped_column(String(16))  # available | in_use | maintenance
