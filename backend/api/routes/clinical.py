"""Patients, doctors and appointments."""

from __future__ import annotations

from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from agents.scheduling_agent import predict_duration, suggest_appointment
from core.constants import CRITICAL_SEVERITY, DEPARTMENTS
from core.deps import ADMIN, ADMIN_DOCTOR, ALL_ROLES, require_roles
from database.session import get_db
from models import Appointment, Bed, Doctor, Patient, User
from schemas import (
    AppointmentCreate, AppointmentCreated, AppointmentOut, DoctorOut, Page, PatientCreate, PatientOut,
)
from services.hospital_state import day_bounds, doctor_loads, get_now

router = APIRouter(tags=["clinical"])


def _check_department(dept: str | None) -> None:
    if dept is not None and dept not in DEPARTMENTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown department '{dept}'. Valid: {', '.join(DEPARTMENTS)}")


def _appointment_out(a: Appointment) -> AppointmentOut:
    return AppointmentOut(id=a.id, appointment_id=a.appointment_id, patient_id=a.patient_id,
                          patient_name=a.patient.name, doctor_id=a.doctor_id, doctor_name=a.doctor.name,
                          department=a.doctor.specialization, appointment_time=a.appointment_time,
                          consultation_duration=a.consultation_duration, wait_time=a.wait_time, status=a.status)


# ---------------------------------------------------------------- patients
@router.get("/patients", response_model=Page[PatientOut], summary="List patients (doctors see their own)")
def list_patients(search: str | None = None, department: str | None = None,
                  status_filter: str = Query("admitted", alias="status", pattern="^(admitted|discharged|all)$"),
                  limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                  db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_DOCTOR))):
    _check_department(department)
    q = select(Patient)
    if user.role == "doctor":
        q = q.where(Patient.patient_id.in_(select(Appointment.patient_id).where(Appointment.doctor_id == user.doctor_id)))
    if search:
        like = f"%{search.strip()}%"
        q = q.where(or_(Patient.name.ilike(like), Patient.patient_id.ilike(like)))
    if department:
        q = q.where(Patient.department == department)
    if status_filter == "admitted":
        q = q.where(Patient.discharge_date.is_(None))
    elif status_filter == "discharged":
        q = q.where(Patient.discharge_date.is_not(None))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Patient.admission_date.desc()).limit(limit).offset(offset)).all()
    beds = dict(db.execute(select(Bed.patient_id, Bed.bed_id)
                           .where(Bed.patient_id.in_([p.patient_id for p in rows]))).all())
    items = [PatientOut.model_validate(p).model_copy(update={"bed_id": beds.get(p.patient_id)}) for p in rows]
    return Page(items=items, total=total)


@router.post("/patients", response_model=PatientOut, status_code=201, summary="Admit a patient (admin)")
def create_patient(body: PatientCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN))):
    _check_department(body.department)
    count = db.scalar(select(func.count()).select_from(Patient)) or 0
    duration = body.treatment_duration or (12 if body.severity_score >= CRITICAL_SEVERITY else 3)
    p = Patient(patient_id=f"P{count + 1:05d}", name=body.name, age=body.age, gender=body.gender,
                department=body.department, severity_score=body.severity_score, admission_date=get_now(db),
                discharge_date=None, treatment_duration=duration)
    db.add(p)
    db.commit()
    return PatientOut.model_validate(p)


# ---------------------------------------------------------------- doctors
@router.get("/doctors", response_model=Page[DoctorOut], summary="List doctors with today's load")
def list_doctors(department: str | None = None, db: Session = Depends(get_db),
                 _: User = Depends(require_roles(*ALL_ROLES))):
    _check_department(department)
    q = select(Doctor).order_by(Doctor.doctor_id)
    if department:
        q = q.where(Doctor.specialization == department)
    loads = doctor_loads(db, get_now(db))
    items = [DoctorOut.model_validate(d).model_copy(update={"appointments_today": loads.get(d.doctor_id, 0)})
             for d in db.scalars(q)]
    return Page(items=items, total=len(items))


# ---------------------------------------------------------------- appointments
@router.get("/appointments", response_model=Page[AppointmentOut], summary="List appointments for a day")
def list_appointments(day: date | None = Query(None, alias="date"), doctor_id: str | None = None,
                      status_filter: str | None = Query(None, alias="status"),
                      limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
                      db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN_DOCTOR))):
    ref = datetime.combine(day, datetime.min.time()) if day else get_now(db)
    start, end = day_bounds(ref)
    q = select(Appointment).where(Appointment.appointment_time >= start, Appointment.appointment_time < end)
    if user.role == "doctor":
        q = q.where(Appointment.doctor_id == user.doctor_id)
    elif doctor_id:
        q = q.where(Appointment.doctor_id == doctor_id)
    if status_filter:
        q = q.where(Appointment.status == status_filter)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Appointment.appointment_time).limit(limit).offset(offset)).unique().all()
    return Page(items=[_appointment_out(a) for a in rows], total=total)


@router.post("/appointments", response_model=AppointmentCreated, status_code=201,
             summary="Book an appointment; the Scheduling Agent fills in doctor and slot")
def create_appointment(body: AppointmentCreate, db: Session = Depends(get_db),
                       user: User = Depends(require_roles(*ADMIN_DOCTOR))):
    patient = db.scalar(select(Patient).where(Patient.patient_id == body.patient_id))
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Patient {body.patient_id} not found")
    department = body.department or patient.department
    _check_department(department)
    doctor_id = body.doctor_id or (user.doctor_id if user.role == "doctor" else None)
    suggestion = suggest_appointment(db, department, patient.severity_score, body.preferred_time, doctor_id=doctor_id)
    if not suggestion["doctor_id"]:
        raise HTTPException(status.HTTP_409_CONFLICT, suggestion["reason"])
    count = db.scalar(select(func.count()).select_from(Appointment)) or 0
    appt = Appointment(appointment_id=f"A{count + 1:06d}", patient_id=patient.patient_id,
                       doctor_id=suggestion["doctor_id"], appointment_time=datetime.fromisoformat(suggestion["slot_time"]),
                       consultation_duration=predict_duration(department, patient.severity_score),
                       wait_time=round(suggestion["predicted_wait_min"]), status="scheduled")
    db.add(appt)
    db.commit()
    db.refresh(appt)
    return AppointmentCreated(appointment=_appointment_out(appt), suggestion=suggestion)
