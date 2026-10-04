"""Dashboard: KPIs, trends, ML forecasts and alerts in a single call."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.analytics_agent import demand_forecast
from core.constants import DEPARTMENTS
from core.deps import ALL_ROLES, require_roles
from database.session import get_db
from ml.waiting_time_predictor import WaitingTimePredictor
from models import Appointment, Doctor, EmergencyCase, Patient, Recommendation, Staff, User
from schemas import RecommendationOut
from services.hospital_state import (
    ACTIVE_EMERGENCY, bed_totals, day_bounds, doctor_loads, equipment_summary, get_now, staff_summary, ward_summary,
)

router = APIRouter(tags=["dashboard"])


def _wait_by_department(db: Session, now) -> list[dict]:
    """Predicted wait for the next booking in each department, from current doctor loads (XGBoost)."""
    loads = doctor_loads(db, now)
    start, end = day_bounds(now)
    hour_counts = dict(db.execute(
        select(Doctor.specialization, func.count()).join(Appointment, Appointment.doctor_id == Doctor.doctor_id)
        .where(Appointment.appointment_time >= now.replace(minute=0, second=0),
               Appointment.appointment_time < now.replace(minute=0, second=0) + timedelta(hours=1))
        .group_by(Doctor.specialization)).all())
    rows = []
    for dept in DEPARTMENTS:
        docs = db.scalars(select(Doctor).where(Doctor.specialization == dept, Doctor.availability_status != "off_duty")).all()
        if not docs:
            continue
        avg_load = round(sum(loads.get(d.doctor_id, 0) for d in docs) / len(docs))
        rows.append({"department": dept, "doctor_load": avg_load + 1, "appointments_count": hour_counts.get(dept, 0) + 1})
    try:
        preds = WaitingTimePredictor().predict_many(rows)
    except FileNotFoundError:
        preds = [0.0] * len(rows)
    return [{"department": r["department"], "predicted_wait_min": round(p, 1)} for r, p in zip(rows, preds)]


@router.get("/dashboard", summary="Operational dashboard (all roles)")
def dashboard(db: Session = Depends(get_db), user: User = Depends(require_roles(*ALL_ROLES))) -> dict:
    now = get_now(db)
    start, end = day_bounds(now)
    totals = bed_totals(db)
    staff_total = db.scalar(select(func.count()).select_from(Staff)) or 0
    staff_on = db.scalar(select(func.count()).select_from(Staff).where(Staff.on_duty.is_(True))) or 0
    admissions_today = db.scalar(select(func.count()).select_from(Patient)
                                 .where(Patient.admission_date >= start, Patient.admission_date < end)) or 0
    alerts = db.scalars(select(EmergencyCase).where(EmergencyCase.status.in_(ACTIVE_EMERGENCY))
                        .order_by(EmergencyCase.arrival_time.desc())).all()

    trend_start = start - timedelta(days=13)
    trend_rows = dict(db.execute(select(func.date(Patient.admission_date), func.count())
                                 .where(Patient.admission_date >= trend_start, Patient.admission_date < end)
                                 .group_by(func.date(Patient.admission_date))).all())
    trend = [{"date": (trend_start + timedelta(days=i)).date().isoformat(),
              "admissions": int(trend_rows.get((trend_start + timedelta(days=i)).date(), 0))} for i in range(14)]
    waits = _wait_by_department(db, now)
    equipment = equipment_summary(db)
    eq_usable = sum(e["total"] - e["maintenance"] for e in equipment)
    resource_util = round((totals["occupancy_pct"] + 100 * sum(e["in_use"] for e in equipment) / max(eq_usable, 1)) / 2, 1)
    recs = db.scalars(select(Recommendation).order_by(Recommendation.created_at.desc()).limit(6)).all()

    return {
        "generated_at": now.isoformat(),
        "kpis": {
            "admissions_today": admissions_today,
            "bed_occupancy_pct": totals["occupancy_pct"],
            "icu_occupancy_pct": totals["icu_occupancy_pct"],
            "staff_on_duty": staff_on,
            "staff_total": staff_total,
            "active_emergencies": len(alerts),
            "critical_emergencies": sum(1 for a in alerts if a.severity == "critical"),
            "avg_predicted_wait_min": round(sum(w["predicted_wait_min"] for w in waits) / max(len(waits), 1), 1),
            "resource_utilization_pct": resource_util,
        },
        "admissions_trend": trend,
        "demand_forecast": [{"date": f["date"], "expected_admissions": f["expected_admissions"]}
                            for f in demand_forecast(db, 7)],
        "occupancy_by_ward": [{k: w[k] for k in ("ward", "total", "occupied", "available", "occupancy_pct")}
                              for w in ward_summary(db)],
        "staff_by_department": [{k: s[k] for k in ("department", "on_duty", "total", "avg_workload")}
                                for s in staff_summary(db)],
        "wait_time_by_department": waits,
        "emergency_alerts": [{"case_id": a.case_id, "severity": a.severity, "department": a.department,
                              "arrival_time": a.arrival_time.isoformat(), "status": a.status} for a in alerts[:10]],
        "equipment_utilization": [{k: e[k] for k in ("type", "total", "in_use", "utilization_pct")} for e in equipment],
        "recent_recommendations": [RecommendationOut.model_validate(r).model_dump(mode="json") for r in recs],
    }
