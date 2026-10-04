"""Agent 4 - Emergency Response Agent.

Detects emergency surges, reserves ICU beds for critical cases (after the Resource Agent's
allocations), assigns surgeons, forecasts tomorrow's bed requirement (XGBoost) and raises
administrator alerts.

Output (emergency_status): {"priority_level": "Critical", "recommended_actions": [...], ...}
"""

from __future__ import annotations

import math

from langchain_core.runnables import RunnableConfig
from sqlalchemy import func, select

from agents.base import constraint_list, db_from, finish
from ml.bed_demand_predictor import BedDemandPredictor
from models import Bed, EmergencyCase, Patient
from services.hospital_state import bed_totals, day_bounds, emergency_surge, get_now, on_duty_staff


def _priority(surge: dict, shortfall: int) -> str:
    if shortfall > 0 or surge["critical_cases"] >= 3 or surge["surge_detected"]:
        return "Critical"
    if surge["critical_cases"] >= 1:
        return "High"
    return "Moderate" if surge["active_cases"] else "Normal"


def emergency_agent(state: dict, config: RunnableConfig) -> dict:
    db = db_from(config)
    now = get_now(db)
    surge = emergency_surge(db)
    excluded = constraint_list(state, "emergency", "exclude_beds")

    # ICU beds still free after the Resource Agent's proposed allocations.
    taken = {a["assigned_bed"] for a in (state.get("resource_status") or {}).get("assignments", [])}
    free_icu = [b.bed_id for b in db.scalars(select(Bed).where(Bed.bed_type == "icu",
                                                               Bed.occupancy_status == "available")
                                             .order_by(Bed.bed_id))
                if b.bed_id not in taken and b.bed_id not in excluded]
    critical_waiting = db.scalar(select(func.count()).select_from(EmergencyCase)
                                 .where(EmergencyCase.status == "waiting", EmergencyCase.severity == "critical")) or 0
    reserve = min(critical_waiting, len(free_icu))
    shortfall = critical_waiting - reserve
    surgeons = [s for s in on_duty_staff(db) if s.role == "Surgeon"]
    surgeons_needed = math.ceil(surge["critical_cases"] / 3) if surge["critical_cases"] else 0

    start, end = day_bounds(now)
    admissions_today = db.scalar(select(func.count()).select_from(Patient)
                                 .where(Patient.admission_date >= start, Patient.admission_date < end)) or 0
    emergencies_today = db.scalar(select(func.count()).select_from(EmergencyCase)
                                  .where(EmergencyCase.arrival_time >= start, EmergencyCase.arrival_time < end)) or 0
    totals = bed_totals(db)
    try:
        beds_tomorrow = round(BedDemandPredictor().predict(totals["occupancy_pct"] / 100, admissions_today,
                                                           emergencies_today))
    except FileNotFoundError:
        beds_tomorrow = None

    actions = []
    if reserve:
        actions.append(f"Reserve {reserve} ICU bed{'s' if reserve > 1 else ''}")
    if surgeons_needed:
        assign = min(surgeons_needed, len(surgeons))
        actions.append(f"Assign {assign} surgeon{'s' if assign != 1 else ''}"
                       + (f" (need {surgeons_needed}, {len(surgeons)} on duty)" if assign < surgeons_needed else ""))
    if shortfall:
        actions.append(f"Divert or transfer {shortfall} critical case(s): no ICU capacity left")
    if surge["surge_detected"]:
        actions.append("Activate surge protocol and call in off-duty emergency staff")
    if surge["surge_detected"] or shortfall or surge["critical_cases"] >= 3:
        actions.append("Alert on-call administrator")
    if beds_tomorrow and beds_tomorrow > totals["usable"] * 0.9:
        actions.append(f"Plan discharges: forecast {beds_tomorrow} occupied beds tomorrow vs {totals['usable']} usable")

    output = {
        "priority_level": _priority(surge, shortfall),
        "recommended_actions": actions or ["No action needed: emergency department within normal range"],
        "reserved_beds": free_icu[:reserve],
        "surge_detected": surge["surge_detected"],
        "surge": surge,
        "critical_waiting": critical_waiting,
        "icu_free_after_allocation": len(free_icu),
        "icu_shortfall": shortfall,
        "surgeons_on_duty": len(surgeons),
        "forecast_beds_tomorrow": beds_tomorrow,
        "solver_status": "INFEASIBLE" if shortfall else "OPTIMAL",
        "reason": (f"{critical_waiting} critical emergency case(s) need ICU beds but only {len(free_icu)} ICU "
                   f"bed(s) remain free after inpatient allocation." if shortfall else None),
    }
    summary = (f"Priority {output['priority_level']}: {surge['active_cases']} active cases "
               f"({surge['critical_cases']} critical), reserve {reserve} ICU bed(s)"
               + (f", ICU shortfall {shortfall}" if shortfall else ""))
    return finish(state, "emergency", "emergency_status", output, summary)
