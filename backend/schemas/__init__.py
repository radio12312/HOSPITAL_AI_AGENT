"""Pydantic request/response schemas for the REST API (see docs/API.md)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int


# ---------------------------------------------------------------- auth
class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(ORM):
    id: int
    username: str
    email: str
    role: str
    doctor_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------- clinical
class PatientOut(ORM):
    id: int
    patient_id: str
    name: str
    age: int
    gender: str
    department: str
    severity_score: float
    admission_date: datetime
    discharge_date: datetime | None
    treatment_duration: int
    bed_id: str | None = None


class PatientCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    age: int = Field(ge=0, le=120)
    gender: str = Field(min_length=1, max_length=16)
    department: str
    severity_score: float = Field(ge=1.0, le=10.0)
    treatment_duration: int | None = Field(default=None, ge=1, le=60)


class DoctorOut(ORM):
    id: int
    doctor_id: str
    name: str
    specialization: str
    experience_years: int
    daily_capacity: int
    availability_status: str
    appointments_today: int = 0


class AppointmentOut(BaseModel):
    id: int
    appointment_id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    department: str
    appointment_time: datetime
    consultation_duration: int
    wait_time: int
    status: str


class AppointmentCreate(BaseModel):
    patient_id: str
    department: str | None = None
    doctor_id: str | None = None
    preferred_time: datetime | None = None


class AppointmentCreated(BaseModel):
    appointment: AppointmentOut
    suggestion: dict[str, Any]


class EmergencyCaseOut(ORM):
    id: int
    case_id: str
    severity: str
    arrival_time: datetime
    department: str
    response_time: int | None
    status: str


class EmergencyCreate(BaseModel):
    severity: Literal["critical", "high", "moderate", "low"]
    department: str = "Emergency"
    count: int = Field(default=1, ge=1, le=50)


# ---------------------------------------------------------------- resources
class BedOut(BaseModel):
    id: int
    bed_id: str
    ward: str
    bed_type: str
    occupancy_status: str
    patient_id: str | None
    patient_name: str | None


class BedAllocateRequest(BaseModel):
    patient_ids: list[str] | None = None


class StaffOut(ORM):
    id: int
    staff_id: str
    name: str
    role: str
    department: str
    shift: str
    workload_score: float
    on_duty: bool


class RebalanceRequest(BaseModel):
    apply: bool = False


# ---------------------------------------------------------------- agent
class AgentQuery(BaseModel):
    query: str = Field(min_length=2, max_length=1000)


class AgentResume(BaseModel):
    thread_id: str
    action: Literal["approve", "reject"]
    note: str = ""


class RecommendationOut(ORM):
    id: int
    agent: str
    title: str
    details: dict[str, Any]
    status: str
    created_at: datetime
    decided_by: str | None
    override_note: str | None


class RecommendationDecision(BaseModel):
    action: Literal["accept", "override"]
    note: str = ""
