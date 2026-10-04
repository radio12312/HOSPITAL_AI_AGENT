"""Agent 2 - Resource Allocation Agent.

Allocates beds to admitted patients who are waiting (OR-Tools CP-SAT), monitors ward
occupancy and flags constrained equipment.

Output (resource_status): {"assigned_bed": "ICU-12", "utilization_score": 92, ...}
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agents.base import constraint_list, db_from, finish
from optimization.bed_optimizer import optimize_beds
from services.hospital_state import (
    bed_totals, equipment_summary, free_bed_slots, to_need, waiting_for_bed, ward_summary,
)

CONSTRAINED_PCT = 85.0


def plan_beds(db, patient_ids: list[str] | None = None, excluded_beds: set[str] | None = None,
              reserve_icu: int = 0):
    """Run the bed optimiser on the live state. Shared with POST /beds/allocate."""
    waiting = waiting_for_bed(db)
    if patient_ids is not None:
        waiting = [p for p in waiting if p.patient_id in set(patient_ids)]
    totals = bed_totals(db)
    return optimize_beds([to_need(p) for p in waiting], free_bed_slots(db), occupied_count=totals["occupied"],
                         usable_total=totals["usable"], reserve_icu=reserve_icu, excluded_beds=excluded_beds)


def resource_agent(state: dict, config: RunnableConfig) -> dict:
    db = db_from(config)
    excluded = constraint_list(state, "resource", "exclude_beds")
    plan = plan_beds(db, excluded_beds=excluded)
    wards = ward_summary(db)
    equipment = equipment_summary(db)
    constrained = ([f"{w['ward']} ward ({w['occupancy_pct']}% occupied)" for w in wards
                    if w["occupancy_pct"] >= CONSTRAINED_PCT]
                   + [f"{e['type']} ({e['utilization_pct']}% in use)" for e in equipment
                      if e["utilization_pct"] >= CONSTRAINED_PCT])
    output = {
        "assigned_bed": plan.assignments[0]["assigned_bed"] if plan.assignments else None,
        "utilization_score": plan.utilization_score,
        "assignments": plan.assignments,
        "unassigned": plan.unassigned,
        "solver_status": plan.solver_status,
        "reason": plan.reason,
        "ward_utilization": wards,
        "equipment": equipment,
        "constrained_resources": constrained,
        "excluded_beds": sorted(excluded),
    }
    summary = (f"Placed {len(plan.assignments)} waiting patient(s), {len(plan.unassigned)} unplaced; "
               f"utilization {plan.utilization_score}%; solver {plan.solver_status}")
    return finish(state, "resource", "resource_status", output, summary)
