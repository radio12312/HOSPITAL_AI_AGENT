"""Patients, doctors, appointments and emergency cases."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.session import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    age: Mapped[int] = mapped_column(Integer)
    gender: Mapped[str] = mapped_column(String(16))
    department: Mapped[str] = mapped_column(String(40), index=True)
    severity_score: Mapped[float] = mapped_column(Float)  # 1.0 - 10.0, >= 8 critical
    admission_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    discharge_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    treatment_duration: Mapped[int] = mapped_column(Integer)  # days

    @property
    def is_critical(self) -> bool:
        return self.severity_score >= 8.0


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(primary_key=True)
    doctor_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    specialization: Mapped[str] = mapped_column(String(40), index=True)
    experience_years: Mapped[int] = mapped_column(Integer)
    daily_capacity: Mapped[int] = mapped_column(Integer)  # appointments per day
    availability_status: Mapped[str] = mapped_column(String(16))  # available | busy | off_duty


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(primary_key=True)
    appointment_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.patient_id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.doctor_id"), index=True)
    appointment_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    consultation_duration: Mapped[int] = mapped_column(Integer)  # minutes
    wait_time: Mapped[int] = mapped_column(Integer)  # minutes
    status: Mapped[str] = mapped_column(String(16), index=True)  # scheduled | completed | cancelled | no_show

    patient: Mapped[Patient] = relationship(lazy="joined")
    doctor: Mapped[Doctor] = relationship(lazy="joined")


class EmergencyCase(Base):
    __tablename__ = "emergency_cases"

    id: Mapped[int] = mapped_column(primary_key=True)
    case_id: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)  # critical | high | moderate | low
    arrival_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    department: Mapped[str] = mapped_column(String(40))
    response_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # minutes
    status: Mapped[str] = mapped_column(String(16), index=True)  # waiting | in_treatment | resolved
