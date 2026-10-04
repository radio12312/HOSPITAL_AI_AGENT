"""Bed allocation with OR-Tools CP-SAT.

Hard constraints
  * one patient per bed, at most one bed per patient, only `available` beds
  * critical patients (severity >= 8) only in ICU beds
  * non-critical patients never take ICU beds unless severity >= 6 (high acuity)
  * children (< 16) go to pediatric beds unless critical
  * optionally keep `reserve_icu` ICU beds free for incoming emergencies
Objective
  bed as many patients as possible, prioritising severity, then prefer the department's ward.

Patients that cannot be placed are returned with a reason and the plan is INFEASIBLE.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ortools.sat.python import cp_model

from core.constants import CRITICAL_SEVERITY, DEPARTMENT_WARD, HIGH_SEVERITY


@dataclass(frozen=True)
class PatientNeed:
    patient_id: str
    name: str
    severity_score: float
    department: str
    age: int


@dataclass(frozen=True)
class BedSlot:
    bed_id: str
    ward: str
    bed_type: str


@dataclass
class BedPlan:
    assignments: list[dict] = field(default_factory=list)
    unassigned: list[dict] = field(default_factory=list)
    utilization_score: int = 0
    solver_status: str = "OPTIMAL"  # OPTIMAL | FEASIBLE | INFEASIBLE
    reason: str | None = None


def preferred_ward(p: PatientNeed) -> str:
    if p.severity_score >= CRITICAL_SEVERITY:
        return "ICU"
    if p.age < 16:
        return "Pediatrics"
    return DEPARTMENT_WARD.get(p.department, "General")


def allowed(p: PatientNeed, bed: BedSlot) -> bool:
    """Hard bed-type rule (also used by the reviewer to verify plans)."""
    if p.severity_score >= CRITICAL_SEVERITY:
        return bed.bed_type == "icu"
    if bed.bed_type == "icu":
        return p.severity_score >= HIGH_SEVERITY
    if p.age < 16:
        return bed.bed_type == "pediatric"
    return bed.bed_type != "pediatric"


def optimize_beds(patients: list[PatientNeed], free_beds: list[BedSlot], *, occupied_count: int = 0,
                  usable_total: int | None = None, reserve_icu: int = 0,
                  excluded_beds: set[str] | None = None, time_limit_s: float = 10.0) -> BedPlan:
    excluded_beds = excluded_beds or set()
    beds = [b for b in free_beds if b.bed_id not in excluded_beds]
    model = cp_model.CpModel()
    x = {(p.patient_id, b.bed_id): model.NewBoolVar(f"x_{p.patient_id}_{b.bed_id}")
         for p in patients for b in beds if allowed(p, b)}

    for p in patients:
        model.AddAtMostOne(v for (pid, _), v in x.items() if pid == p.patient_id)
    for b in beds:
        model.AddAtMostOne(v for (_, bid), v in x.items() if bid == b.bed_id)
    icu_free = [b for b in beds if b.bed_type == "icu"]
    if reserve_icu:
        usable_icu = max(0, len(icu_free) - reserve_icu)
        model.Add(sum(v for (_, bid), v in x.items() if bid in {b.bed_id for b in icu_free}) <= usable_icu)

    by_id = {p.patient_id: p for p in patients}
    bed_by_id = {b.bed_id: b for b in beds}
    objective = []
    for (pid, bid), v in x.items():
        p, b = by_id[pid], bed_by_id[bid]
        score = 1000 + int(p.severity_score * 100)  # bed everyone, sickest first
        if b.ward == preferred_ward(p):
            score += 50
        elif b.bed_type == "icu":
            score -= 80  # don't spend ICU capacity on non-critical patients unless needed
        objective.append(score * v)
    model.Maximize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1  # deterministic: an applied plan matches its preview
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("bed model could not be solved")

    plan = BedPlan()
    placed = set()
    for (pid, bid), v in sorted(x.items()):
        if solver.Value(v):
            p, b = by_id[pid], bed_by_id[bid]
            placed.add(pid)
            plan.assignments.append({"patient_id": pid, "patient_name": p.name, "severity_score": p.severity_score,
                                     "assigned_bed": bid, "ward": b.ward})
    plan.assignments.sort(key=lambda a: -a["severity_score"])
    for p in sorted(patients, key=lambda p: -p.severity_score):
        if p.patient_id in placed:
            continue
        need = "ICU" if p.severity_score >= CRITICAL_SEVERITY else preferred_ward(p)
        plan.unassigned.append({"patient_id": p.patient_id, "reason": f"No {need} bed available"})

    total = usable_total or (occupied_count + len(free_beds))
    plan.utilization_score = round(100 * (occupied_count + len(plan.assignments)) / max(total, 1))
    if plan.unassigned:
        crit = sum(1 for p in patients if p.severity_score >= CRITICAL_SEVERITY)
        plan.solver_status = "INFEASIBLE"
        plan.reason = (f"{len(plan.unassigned)} of {len(patients)} patients cannot be bedded: {crit} critical "
                       f"patients need ICU beds and {len(icu_free)} ICU beds are free"
                       + (f" ({reserve_icu} held in reserve)" if reserve_icu else "") + ".")
    else:
        plan.solver_status = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
    return plan
