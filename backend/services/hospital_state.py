"""Read-side queries over the live hospital state, shared by the API, agents and simulator.

"Now" is the hospital clock stored in `system_state.sim_now` (set at seeding, moved by
scenarios), so the dashboard stays meaningful no matter when the app is opened.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.constants import CRITICAL_SEVERITY, WARD_NAMES
from models import Appointment, Bed, Doctor, EmergencyCase, Equipment, Patient, Staff, SystemState
from optimization.bed_optimizer import BedSlot, PatientNeed
from optimization.staff_optimizer import StaffMember, required_staff

ACTIVE_EMERGENCY = ("waiting", "in_treatment")


# ---------------------------------------------------------------- clock

def get_now(db: Session) -> datetime:
    row = db.get(SystemState, "sim_now")
    return datetime.fromisoformat(row.value) if row else datetime.now().replace(second=0, microsecond=0)


def set_state(db: Session, key: str, value: str) -> None:
    row = db.get(SystemState, key)
    if row:
        row.value = value
    else:
        db.add(SystemState(key=key, value=value))


# ---------------------------------------------------------------- patients & beds

def admitted_patients_query():
    return select(Patient).where(Patient.discharge_date.is_(None))


def waiting_for_bed(db: Session) -> list[Patient]:
    bedded = select(Bed.patient_id).where(Bed.patient_id.is_not(None))
    q = admitted_patients_query().where(Patient.patient_id.not_in(bedded)).order_by(Patient.severity_score.desc())
    return list(db.scalars(q))


def to_need(p: Patient) -> PatientNeed:
    return PatientNeed(p.patient_id, p.name, p.severity_score, p.department, p.age)


def free_bed_slots(db: Session) -> list[BedSlot]:
    beds = db.scalars(select(Bed).where(Bed.occupancy_status == "available").order_by(Bed.bed_id))
    return [BedSlot(b.bed_id, b.ward, b.bed_type) for b in beds]


def ward_summary(db: Session) -> list[dict]:
    rows = db.execute(select(Bed.ward, Bed.occupancy_status, func.count()).group_by(Bed.ward, Bed.occupancy_status))
    agg: dict[str, Counter] = defaultdict(Counter)
    for ward, status, n in rows:
        agg[ward][status] += n
    out = []
    for ward in WARD_NAMES:
        c = agg.get(ward, Counter())
        total = sum(c.values())
        usable = total - c["maintenance"]
        occupied = c["occupied"] + c["reserved"]
        out.append({"ward": ward, "total": total, "occupied": c["occupied"], "reserved": c["reserved"],
                    "maintenance": c["maintenance"], "available": c["available"],
                    "occupancy_pct": round(100 * occupied / usable, 1) if usable else 0.0})
    return out


def bed_totals(db: Session) -> dict:
    summary = ward_summary(db)
    usable = sum(w["total"] - w["maintenance"] for w in summary)
    occupied = sum(w["occupied"] + w["reserved"] for w in summary)
    icu = next(w for w in summary if w["ward"] == "ICU")
    return {"usable": usable, "occupied": occupied, "occupancy_pct": round(100 * occupied / max(usable, 1), 1),
            "icu_occupancy_pct": icu["occupancy_pct"], "icu_free": icu["available"]}


# ---------------------------------------------------------------- staff

def patient_load(db: Session) -> dict[str, int]:
    """Current patients per department: admitted inpatients plus active emergency cases."""
    rows = db.execute(admitted_patients_query().with_only_columns(Patient.department, func.count())
                      .group_by(Patient.department))
    load = {d: n for d, n in rows}
    active = db.scalar(select(func.count()).select_from(EmergencyCase)
                       .where(EmergencyCase.status.in_(ACTIVE_EMERGENCY))) or 0
    load["Emergency"] = load.get("Emergency", 0) + active
    return load


def on_duty_staff(db: Session) -> list[Staff]:
    return list(db.scalars(select(Staff).where(Staff.on_duty.is_(True)).order_by(Staff.staff_id)))


def to_member(s: Staff) -> StaffMember:
    return StaffMember(s.staff_id, s.name, s.role, s.department, s.workload_score)


def staff_summary(db: Session) -> list[dict]:
    load = patient_load(db)
    staff = list(db.scalars(select(Staff)))
    by_dept: dict[str, list[Staff]] = defaultdict(list)
    for s in staff:
        by_dept[s.department].append(s)
    out = []
    for dept in sorted(set(by_dept) | set(load)):
        members = by_dept.get(dept, [])
        duty = [s for s in members if s.on_duty]
        out.append({"department": dept, "on_duty": len(duty), "total": len(members),
                    "avg_workload": round(sum(s.workload_score for s in duty) / len(duty), 1) if duty else 0.0,
                    "patient_load": load.get(dept, 0), "required": required_staff(load.get(dept, 0)),
                    "load_ratio": round(load.get(dept, 0) / len(duty), 2) if duty else float(load.get(dept, 0))})
    return out


# ---------------------------------------------------------------- emergency

def emergency_surge(db: Session) -> dict:
    now = get_now(db)
    active = list(db.scalars(select(EmergencyCase).where(EmergencyCase.status.in_(ACTIVE_EMERGENCY))))
    month_ago = now - timedelta(days=30)
    last_30d = db.scalar(select(func.count()).select_from(EmergencyCase)
                         .where(EmergencyCase.arrival_time >= month_ago, EmergencyCase.arrival_time <= now)) or 0
    last_hour = db.scalar(select(func.count()).select_from(EmergencyCase)
                          .where(EmergencyCase.arrival_time >= now - timedelta(hours=1),
                                 EmergencyCase.arrival_time <= now)) or 0
    baseline = last_30d / (30 * 24)
    critical = sum(1 for c in active if c.severity == "critical")
    surge = last_hour >= max(4, 4 * baseline) or critical >= 3
    return {"active_cases": len(active), "critical_cases": critical, "baseline_per_hour": round(baseline, 2),
            "last_hour": int(last_hour), "surge_detected": bool(surge)}


def critical_waiting(db: Session) -> list[Patient]:
    return [p for p in waiting_for_bed(db) if p.severity_score >= CRITICAL_SEVERITY]


# ---------------------------------------------------------------- equipment & doctors

def equipment_summary(db: Session) -> list[dict]:
    rows = db.execute(select(Equipment.type, Equipment.availability_status, func.count())
                      .group_by(Equipment.type, Equipment.availability_status))
    agg: dict[str, Counter] = defaultdict(Counter)
    for t, status, n in rows:
        agg[t][status] += n
    return [{"type": t, "total": sum(c.values()), "in_use": c["in_use"], "available": c["available"],
             "maintenance": c["maintenance"],
             "utilization_pct": round(100 * c["in_use"] / max(sum(c.values()) - c["maintenance"], 1), 1)}
            for t, c in sorted(agg.items())]


def day_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def doctor_loads(db: Session, day: datetime) -> dict[str, int]:
    start, end = day_bounds(day)
    rows = db.execute(select(Appointment.doctor_id, func.count())
                      .where(Appointment.appointment_time >= start, Appointment.appointment_time < end,
                             Appointment.status != "cancelled")
                      .group_by(Appointment.doctor_id))
    return {d: n for d, n in rows}


def doctors_by_department(db: Session, department: str) -> list[Doctor]:
    return list(db.scalars(select(Doctor).where(Doctor.specialization == department).order_by(Doctor.doctor_id)))
