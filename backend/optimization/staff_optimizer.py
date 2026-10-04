"""Staff reallocation with OR-Tools CP-SAT.

Each department needs ceil(patient_load / TARGET_PATIENTS_PER_STAFF) on-duty staff.
Movable on-duty staff (nurses, technicians, paramedics) can be reassigned between departments.

Hard constraints
  * a moved staff member's workload (+ MOVE_WORKLOAD for an unfamiliar department) stays <= WORKLOAD_CAP
  * every department with patients keeps at least one staff member
  * excluded staff (e.g. flagged by the reviewer) are never moved
Objective
  minimise total staffing shortfall, then the number of moves, then load on the busiest people.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from core.constants import MOVABLE_ROLES, TARGET_PATIENTS_PER_STAFF, WORKLOAD_CAP

MOVE_WORKLOAD = 8.0  # extra workload for working in an unfamiliar department


@dataclass(frozen=True)
class StaffMember:
    staff_id: str
    name: str
    role: str
    department: str
    workload_score: float


@dataclass
class StaffPlan:
    staff_reallocation: list[dict] = field(default_factory=list)
    moves: list[dict] = field(default_factory=list)  # per person: staff_id, from, to, new_workload
    before: list[dict] = field(default_factory=list)
    after: list[dict] = field(default_factory=list)
    solver_status: str = "OPTIMAL"
    reason: str | None = None


def required_staff(load: int) -> int:
    return math.ceil(load / TARGET_PATIENTS_PER_STAFF) if load > 0 else 0


def _ratios(counts: dict[str, int], load: dict[str, int]) -> list[dict]:
    return [{"department": d, "staff": counts.get(d, 0), "patient_load": load.get(d, 0),
             "required": required_staff(load.get(d, 0)),
             "load_ratio": round(load.get(d, 0) / counts[d], 2) if counts.get(d) else float(load.get(d, 0))}
            for d in sorted(set(load) | set(counts))]


def optimize_staff(on_duty: list[StaffMember], patient_load: dict[str, int], *,
                   excluded_staff: set[str] | None = None, max_moves: int = 12,
                   time_limit_s: float = 10.0) -> StaffPlan:
    excluded_staff = excluded_staff or set()
    depts = sorted(set(patient_load) | {s.department for s in on_duty})
    movable = [s for s in on_duty if s.role in MOVABLE_ROLES and s.staff_id not in excluded_staff]
    fixed = defaultdict(int)
    for s in on_duty:
        if s not in movable:
            fixed[s.department] += 1

    model = cp_model.CpModel()
    x: dict[tuple[str, str], cp_model.IntVar] = {}
    for s in movable:
        for d in depts:
            if d != s.department and s.workload_score + MOVE_WORKLOAD > WORKLOAD_CAP:
                continue  # moving this person would breach the workload cap
            x[s.staff_id, d] = model.NewBoolVar(f"x_{s.staff_id}_{d}")
        model.AddExactlyOne(v for (sid, _), v in x.items() if sid == s.staff_id)

    count = {d: fixed[d] + sum(v for (_, dd), v in x.items() if dd == d) for d in depts}
    shortfall = {}
    for d in depts:
        req = required_staff(patient_load.get(d, 0))
        shortfall[d] = model.NewIntVar(0, max(req, 0), f"short_{d}")
        model.Add(count[d] + shortfall[d] >= req)
        if patient_load.get(d, 0) > 0:
            model.Add(count[d] >= 1)
    moved = [v for (sid, d), v in x.items() if d != next(s.department for s in movable if s.staff_id == sid)]
    model.Add(sum(moved) <= max_moves)
    by_id = {s.staff_id: s for s in movable}
    busy_cost = sum(int(by_id[sid].workload_score) * v for (sid, d), v in x.items() if d != by_id[sid].department)
    model.Minimize(10_000 * sum(shortfall.values()) + 100 * sum(moved) + busy_cost)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1  # deterministic: an applied plan matches its preview
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("staff model could not be solved")

    before_counts = defaultdict(int)
    for s in on_duty:
        before_counts[s.department] += 1
    after_counts = dict(before_counts)
    plan = StaffPlan()
    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for (sid, d), v in sorted(x.items()):
        s = by_id[sid]
        if solver.Value(v) and d != s.department:
            grouped[s.department, d].append(sid)
            after_counts[s.department] -= 1
            after_counts[d] = after_counts.get(d, 0) + 1
            plan.moves.append({"staff_id": sid, "name": s.name, "from": s.department, "to": d,
                               "new_workload": round(s.workload_score + MOVE_WORKLOAD, 1)})
    plan.staff_reallocation = [{"from": f, "to": t, "staff_count": len(ids), "staff_ids": ids}
                               for (f, t), ids in sorted(grouped.items(), key=lambda kv: -len(kv[1]))]
    plan.before = _ratios(dict(before_counts), patient_load)
    plan.after = _ratios(after_counts, patient_load)

    gaps = {d: solver.Value(v) for d, v in shortfall.items() if solver.Value(v) > 0}
    if gaps:
        plan.solver_status = "INFEASIBLE"
        plan.reason = ("Not enough movable staff within the workload cap: short "
                       + ", ".join(f"{n} in {d}" for d, n in gaps.items()) + ".")
    else:
        plan.solver_status = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    return plan
