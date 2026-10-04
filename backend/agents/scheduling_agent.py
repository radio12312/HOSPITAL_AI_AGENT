"""Agent 1 - Patient Scheduling Agent.

Matches patients with doctors, predicts consultation duration and waiting time (XGBoost),
finds a conflict-free slot, and flags overloaded doctors.

Tools: appointment database (today's bookings per doctor) and doctor availability.
Output (appointment_info): {"doctor", "recommended_slot", "predicted_wait_time", ...}
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select
from sqlalchemy.orm import Session

from agents.base import constraint_list, db_from, finish
from core.constants import DEPARTMENT_WEIGHTS
from ml.waiting_time_predictor import WaitingTimePredictor
from models import Appointment, Doctor, Patient
from seed.generator import DEPT_CONSULT_MIN
from services.hospital_state import day_bounds, doctor_loads, doctors_by_department, get_now

CLINIC_END_HOUR = 18
SLOT_MINUTES = 15


def predict_duration(department: str, severity: float) -> int:
    """Consultation length heuristic mirroring the synthetic data generator."""
    return int(max(8, min(60, round(DEPT_CONSULT_MIN.get(department, 18) + 1.5 * (severity - 5)))))


def _bookings(db: Session, doctor_id: str, day: datetime) -> list[tuple[datetime, datetime]]:
    start, end = day_bounds(day)
    rows = db.scalars(select(Appointment).where(Appointment.doctor_id == doctor_id,
                                                Appointment.appointment_time >= start,
                                                Appointment.appointment_time < end,
                                                Appointment.status.in_(["scheduled", "completed"])))
    return [(a.appointment_time, a.appointment_time + timedelta(minutes=a.consultation_duration)) for a in rows]


def _first_free_slot(busy: list[tuple[datetime, datetime]], earliest: datetime, duration: int) -> datetime | None:
    t = earliest
    end_of_day = earliest.replace(hour=CLINIC_END_HOUR, minute=0)
    while t + timedelta(minutes=duration) <= end_of_day:
        if all(t + timedelta(minutes=duration) <= s or t >= e for s, e in busy):
            return t
        t += timedelta(minutes=SLOT_MINUTES)
    return None


def _round_up(t: datetime) -> datetime:
    extra = (-t.minute) % SLOT_MINUTES
    return (t + timedelta(minutes=extra)).replace(second=0, microsecond=0)


def suggest_appointment(db: Session, department: str, severity: float = 5.0,
                        preferred_time: datetime | None = None, exclude_doctors: set[str] | None = None,
                        doctor_id: str | None = None) -> dict:
    """Pick the doctor + slot with the lowest predicted wait. Used by the agent and POST /appointments."""
    now = get_now(db)
    earliest = _round_up(max(preferred_time or now, now))
    loads = doctor_loads(db, earliest)
    predictor = WaitingTimePredictor()
    duration = predict_duration(department, severity)
    candidates = []
    doctors = doctors_by_department(db, department)
    bookings = {d.doctor_id: _bookings(db, d.doctor_id, earliest) for d in doctors}
    for doc in doctors:
        if doctor_id and doc.doctor_id != doctor_id:
            continue
        if doc.availability_status == "off_duty" or doc.doctor_id in (exclude_doctors or set()):
            continue
        slot = _first_free_slot(bookings[doc.doctor_id], earliest, duration)
        if slot is None:
            continue
        same_hour = sum(1 for b in bookings.values() for s, _ in b if s.hour == slot.hour)
        wait = predictor.predict(loads.get(doc.doctor_id, 0) + 1, same_hour + 1, department)
        delay = (slot - earliest).total_seconds() / 60
        candidates.append((wait + 0.5 * delay, doc, slot, wait, loads.get(doc.doctor_id, 0)))
    if not candidates:
        return {"doctor": None, "doctor_id": None, "recommended_slot": None, "predicted_wait_time": None,
                "department": department, "reason": f"No available {department} doctor has a free slot today."}
    _, doc, slot, wait, load = min(candidates, key=lambda c: c[0])
    return {"doctor": doc.name, "doctor_id": doc.doctor_id, "department": department,
            "recommended_slot": slot.strftime("%I:%M %p").lstrip("0"), "slot_time": slot.isoformat(),
            "predicted_wait_time": f"{round(wait)} min", "predicted_wait_min": round(wait, 1),
            "predicted_duration_min": duration,
            "reason": (f"Lowest predicted wait among {len(candidates)} available {department} doctors "
                       f"(current load {load}/{doc.daily_capacity}); slot has no booking conflicts.")}


def scheduling_agent(state: dict, config: RunnableConfig) -> dict:
    db = db_from(config)
    now = get_now(db)
    exclude = constraint_list(state, "scheduling", "exclude_doctors")
    info = state.get("patient_info") or {}

    if info.get("patient_id"):
        patient = db.scalar(select(Patient).where(Patient.patient_id == info["patient_id"]))
        department = info.get("department") or (patient.department if patient else "General Medicine")
        severity = patient.severity_score if patient else 5.0
    else:
        # No specific patient: schedule for the busiest department today.
        start, end = day_bounds(now)
        rows = db.execute(select(Doctor.specialization).join(Appointment, Appointment.doctor_id == Doctor.doctor_id)
                          .where(Appointment.appointment_time >= start, Appointment.appointment_time < end))
        busiest = Counter(r[0] for r in rows).most_common(1)
        department = busiest[0][0] if busiest else max(DEPARTMENT_WEIGHTS, key=DEPARTMENT_WEIGHTS.get)
        severity = 5.0

    suggestion = suggest_appointment(db, department, severity, exclude_doctors=exclude)
    loads = doctor_loads(db, now)
    overloaded = []
    for doc in db.scalars(select(Doctor)):
        n = loads.get(doc.doctor_id, 0)
        if n > doc.daily_capacity:
            overloaded.append({"doctor_id": doc.doctor_id, "doctor": doc.name, "department": doc.specialization,
                               "appointments_today": n, "daily_capacity": doc.daily_capacity})
    overloaded.sort(key=lambda d: d["appointments_today"] - d["daily_capacity"], reverse=True)

    output = {**suggestion, "overloaded_doctors": overloaded[:8], "appointments_today": sum(loads.values()),
              "solver_status": "OPTIMAL" if suggestion["doctor"] else "INFEASIBLE"}
    summary = (f"{suggestion['doctor']} at {suggestion['recommended_slot']} for {department} "
               f"(predicted wait {suggestion['predicted_wait_time']}); {len(overloaded)} doctor(s) over capacity"
               if suggestion["doctor"] else suggestion["reason"])
    return finish(state, "scheduling", "appointment_info", output, summary)
