"""Agent 3 - Staff Management Agent.

Balances workload by reallocating movable on-duty staff between departments (OR-Tools CP-SAT)
so each department meets its patients-per-staff target without pushing anyone past the
workload cap.

Output (staff_status): {"staff_reallocation": [{"from": "Ward B", "to": "Ward A", "staff_count": 3}], ...}

Demo mechanism: when `inject_fault` is set (Staff Shortage scenario), the first attempt adds one
move that breaks the workload cap, so the reviewer's revise path can be seen working.
"""

from __future__ import annotations

from langchain_core.runnables import RunnableConfig

from agents.base import constraint_list, db_from, finish
from core.constants import MOVABLE_ROLES, WORKLOAD_CAP
from optimization.staff_optimizer import MOVE_WORKLOAD, StaffPlan, optimize_staff
from services.hospital_state import on_duty_staff, patient_load, to_member


def plan_staff(db, excluded_staff: set[str] | None = None) -> StaffPlan:
    """Run the staff optimiser on the live state. Shared with POST /staff/rebalance."""
    return optimize_staff([to_member(s) for s in on_duty_staff(db)], patient_load(db), excluded_staff=excluded_staff)


def _inject_fault(db, plan: StaffPlan) -> str | None:
    """DEMO: add a move of the most overloaded movable person (breaks the workload cap)."""
    moved = {m["staff_id"] for m in plan.moves}
    for s in sorted(on_duty_staff(db), key=lambda s: -s.workload_score):
        if s.role in MOVABLE_ROLES and s.staff_id not in moved and s.workload_score + MOVE_WORKLOAD > WORKLOAD_CAP:
            target = next((r["department"] for r in sorted(plan.after, key=lambda r: -r["load_ratio"])
                           if r["department"] != s.department), "Emergency")
            plan.moves.append({"staff_id": s.staff_id, "name": s.name, "from": s.department, "to": target,
                               "new_workload": round(s.workload_score + MOVE_WORKLOAD, 1)})
            plan.staff_reallocation.append({"from": s.department, "to": target, "staff_count": 1,
                                            "staff_ids": [s.staff_id]})
            return f"moved {s.staff_id} (workload {s.workload_score:g}) to {target}"
    return None


def staff_agent(state: dict, config: RunnableConfig) -> dict:
    db = db_from(config)
    excluded = constraint_list(state, "staff", "exclude_staff")
    plan = plan_staff(db, excluded)
    notes = []
    first_attempt = state.get("attempts", {}).get("staff", 0) == 0
    if state.get("inject_fault") and first_attempt:
        fault = _inject_fault(db, plan)
        if fault:
            notes.append(f"DEMO FAULT INJECTED: {fault}")

    understaffed = [r["department"] for r in plan.before if r["staff"] < r["required"]]
    output = {
        "staff_reallocation": plan.staff_reallocation,
        "moves": plan.moves,
        "before": plan.before,
        "after": plan.after,
        "understaffed_departments": understaffed,
        "solver_status": plan.solver_status,
        "reason": plan.reason,
        "excluded_staff": sorted(excluded),
        "notes": notes,
    }
    summary = (f"{len(plan.moves)} staff move(s) proposed; {len(understaffed)} understaffed department(s) "
               f"before rebalancing; solver {plan.solver_status}" + (f"; {notes[0]}" if notes else ""))
    return finish(state, "staff", "staff_status", output, summary)
