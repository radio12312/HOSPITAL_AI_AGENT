"""Reviewer node: deterministic hard checks on every agent output, then a verdict.

Verdict logic (REVIEWER_MODE=fixed, the default):
  1. any capacity violation / INFEASIBLE solver result -> escalate  (retrying cannot create beds or staff)
  2. outputs identical to the previous attempt           -> escalate  (no progress is being made)
  3. a violation caused by the plan (missing agent)      -> replan    (back to the supervisor)
  4. any other violation                                  -> revise    (back to the offending agents,
                                                                         with violations turned into constraints)
  5. no violations                                         -> approve

REVIEWER_MODE=naive reproduces the original design studied in docs/FAILURE_MODE.md:
steps 1-2 are skipped, every violation is assumed fixable (-> revise) and the LLM writes the
revision feedback.

Every rejection increments `revision_count`; every review is appended to `history`.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timedelta

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from agents.base import db_from
from core.constants import WORKLOAD_CAP
from langgraph_workflow.routing import route_after_review
from langgraph_workflow.state import OPS_AGENTS, Review, Violation
from models import Appointment, Bed, Doctor, Patient, Staff
from optimization.bed_optimizer import BedSlot, allowed
from services.hospital_state import to_need
from services.nvidia_llm import LLMError, chat

OUTPUT_KEYS = {"scheduling": "appointment_info", "resource": "resource_status", "staff": "staff_status",
               "emergency": "emergency_status"}


# ---------------------------------------------------------------- hard checks

def check_resource(db, out: dict) -> list[Violation]:
    vs: list[Violation] = []
    infeasible = out.get("solver_status") == "INFEASIBLE"
    for bed_id, n in Counter(a["assigned_bed"] for a in out.get("assignments", [])).items():
        if n > 1:
            vs.append(Violation(agent="resource", rule="bed_double_booked", subject=bed_id,
                                detail=f"bed {bed_id} assigned to {n} patients"))
    for a in out.get("assignments", []):
        bed = db.scalar(select(Bed).where(Bed.bed_id == a["assigned_bed"]))
        patient = db.scalar(select(Patient).where(Patient.patient_id == a["patient_id"]))
        if bed is None or bed.occupancy_status != "available":
            vs.append(Violation(agent="resource", rule="bed_unavailable", subject=a["assigned_bed"],
                                detail=f"bed {a['assigned_bed']} is not available"))
        elif patient and not allowed(to_need(patient), BedSlot(bed.bed_id, bed.ward, bed.bed_type)):
            vs.append(Violation(agent="resource", rule="bed_type_mismatch", subject=bed.bed_id,
                                detail=f"{patient.patient_id} (severity {patient.severity_score}) in "
                                       f"{bed.bed_type} bed {bed.bed_id}"))
    for u in out.get("unassigned", []):
        vs.append(Violation(agent="resource", rule="patient_unbedded", subject=u["patient_id"],
                            cause="capacity" if infeasible else "execution",
                            detail=f"{u['patient_id']}: {u['reason']}"))
    return vs


def check_staff(db, out: dict) -> list[Violation]:
    vs: list[Violation] = []
    for m in out.get("moves", []):
        s = db.scalar(select(Staff).where(Staff.staff_id == m["staff_id"]))
        if s is None or not s.on_duty:
            vs.append(Violation(agent="staff", rule="staff_not_on_duty", subject=m["staff_id"],
                                detail=f"{m['staff_id']} is not on duty"))
        if m["new_workload"] > WORKLOAD_CAP:
            vs.append(Violation(agent="staff", rule="workload_cap", subject=m["staff_id"],
                                detail=f"{m['staff_id']} would reach workload {m['new_workload']:g} > {WORKLOAD_CAP:g}"))
    for r in out.get("after", []):
        if r["patient_load"] > 0 and r["staff"] == 0:
            vs.append(Violation(agent="staff", rule="department_uncovered", subject=r["department"],
                                detail=f"{r['department']} would have no staff for {r['patient_load']} patients"))
    if out.get("solver_status") == "INFEASIBLE":
        vs.append(Violation(agent="staff", rule="staff_shortfall", cause="capacity", detail=out.get("reason") or ""))
    return vs


def check_scheduling(db, out: dict) -> list[Violation]:
    if not out.get("doctor_id"):
        return [Violation(agent="scheduling", rule="no_slot", cause="capacity", detail=out.get("reason") or "")]
    vs: list[Violation] = []
    doc = db.scalar(select(Doctor).where(Doctor.doctor_id == out["doctor_id"]))
    if doc is None or doc.availability_status == "off_duty":
        vs.append(Violation(agent="scheduling", rule="doctor_unavailable", subject=out["doctor_id"],
                            detail=f"{out['doctor_id']} is off duty"))
    slot = datetime.fromisoformat(out["slot_time"])
    end = slot + timedelta(minutes=out.get("predicted_duration_min", 15))
    clash = db.scalars(select(Appointment).where(Appointment.doctor_id == out["doctor_id"],
                                                 Appointment.status.in_(["scheduled", "completed"]),
                                                 Appointment.appointment_time < end,
                                                 Appointment.appointment_time >= slot - timedelta(hours=2))).all()
    if any(a.appointment_time + timedelta(minutes=a.consultation_duration) > slot for a in clash):
        vs.append(Violation(agent="scheduling", rule="slot_conflict", subject=out["doctor_id"],
                            detail=f"{out['doctor_id']} already booked at {slot:%H:%M}"))
    return vs


def check_emergency(db, out: dict, resource: dict | None) -> list[Violation]:
    vs: list[Violation] = []
    taken = {a["assigned_bed"] for a in (resource or {}).get("assignments", [])}
    for bed_id in out.get("reserved_beds", []):
        bed = db.scalar(select(Bed).where(Bed.bed_id == bed_id))
        if bed_id in taken:
            vs.append(Violation(agent="emergency", rule="bed_double_booked", subject=bed_id,
                                detail=f"{bed_id} reserved for emergencies but also allocated to an inpatient"))
        elif bed is None or bed.occupancy_status != "available" or bed.bed_type != "icu":
            vs.append(Violation(agent="emergency", rule="bed_unavailable", subject=bed_id,
                                detail=f"{bed_id} cannot be reserved (not a free ICU bed)"))
    if out.get("icu_shortfall"):
        vs.append(Violation(agent="emergency", rule="icu_capacity", cause="capacity", detail=out.get("reason") or ""))
    return vs


def check_plan(state: dict) -> list[Violation]:
    """Violations caused by the supervisor's selection rather than by any agent."""
    vs: list[Violation] = []
    selected = set(state.get("selected_agents", []))
    em = state.get("emergency_status") or {}
    if state.get("user_role") == "admin" and em.get("surge_detected") and "staff" not in selected:
        vs.append(Violation(agent="supervisor", rule="missing_agent", subject="staff", cause="plan",
                            detail="Emergency surge detected but staffing was not reviewed"))
    if state.get("user_role") == "admin" and em.get("critical_waiting") and "resource" not in selected:
        vs.append(Violation(agent="supervisor", rule="missing_agent", subject="resource", cause="plan",
                            detail="Critical cases are waiting but bed allocation was not run"))
    return vs


def hard_checks(db, state: dict) -> list[Violation]:
    vs = []
    if state.get("resource_status"):
        vs += check_resource(db, state["resource_status"])
    if state.get("staff_status"):
        vs += check_staff(db, state["staff_status"])
    if state.get("appointment_info"):
        vs += check_scheduling(db, state["appointment_info"])
    if state.get("emergency_status"):
        vs += check_emergency(db, state["emergency_status"], state.get("resource_status"))
    return vs + check_plan(state)


# ---------------------------------------------------------------- feedback

def decisions_hash(state: dict) -> str:
    """Stable hash of the decisions only - used to detect 'no progress'."""
    core = {
        "beds": sorted((a["patient_id"], a["assigned_bed"]) for a in (state.get("resource_status") or {}).get("assignments", [])),
        "staff": sorted((m["staff_id"], m["to"]) for m in (state.get("staff_status") or {}).get("moves", [])),
        "slot": [(state.get("appointment_info") or {}).get(k) for k in ("doctor_id", "slot_time")],
        "reserved": sorted((state.get("emergency_status") or {}).get("reserved_beds", [])),
        "status": [(state.get(k) or {}).get("solver_status") for k in OUTPUT_KEYS.values()],
    }
    return hashlib.sha256(json.dumps(core, sort_keys=True, default=str).encode()).hexdigest()[:16]


_ACTIONS = {
    "workload_cap": "do not move {s}; pick staff with workload headroom",
    "staff_not_on_duty": "only move on-duty staff (not {s})",
    "department_uncovered": "keep at least one staff member in {s}",
    "bed_double_booked": "use bed {s} once only",
    "bed_unavailable": "choose another bed instead of {s}",
    "bed_type_mismatch": "move the patient out of {s} into a bed matching acuity",
    "doctor_unavailable": "pick another doctor than {s}",
    "slot_conflict": "pick a free slot for {s}",
    "missing_agent": "also run the {s} agent",
}


def rule_feedback(vs: list[Violation]) -> str:
    return "Fix: " + " | ".join(f"[{v.agent}] {v.detail} -> {_ACTIONS.get(v.rule, 'resolve this').format(s=v.subject)}"
                                for v in vs)


def updated_constraints(state: dict, vs: list[Violation]) -> dict:
    """Turn violations into solver constraints the agents read on their next attempt."""
    cons = {a: {k: list(v) for k, v in c.items()} for a, c in (state.get("constraints") or {}).items()}

    def add(agent: str, key: str, value: str | None) -> None:
        if value:
            lst = cons.setdefault(agent, {}).setdefault(key, [])
            if value not in lst:
                lst.append(value)

    for v in vs:
        if v.rule in ("workload_cap", "staff_not_on_duty"):
            add("staff", "exclude_staff", v.subject)
        elif v.rule in ("bed_unavailable", "bed_type_mismatch"):
            add(v.agent, "exclude_beds", v.subject)
        elif v.rule == "bed_double_booked":
            add("emergency" if v.agent == "emergency" else "resource", "exclude_beds", v.subject)
        elif v.rule in ("doctor_unavailable", "slot_conflict"):
            add("scheduling", "exclude_doctors", v.subject)
    return cons


def _llm_feedback(state: dict, vs: list[Violation]) -> tuple[str, int]:
    """Naive mode only: ask the LLM how to fix the violations."""
    system = ("You review a hospital operations plan. The plan violates the rules listed. Write 2-4 sentences "
              "of actionable feedback telling the agents how to fix it. Plain text.")
    user = "VIOLATIONS:\n" + "\n".join(f"- [{v.agent}] {v.rule}: {v.detail}" for v in vs)
    try:
        res = chat(system, user, label="reviewer_feedback")
        return res.text, res.api_calls
    except LLMError:
        return rule_feedback(vs), 0


# ---------------------------------------------------------------- node

def decide(state: dict, vs: list[Violation]) -> tuple[Review, int]:
    mode = state.get("reviewer_mode", "fixed")
    agents_with = [a for a in OPS_AGENTS if any(v.agent == a for v in vs)]
    history = state.get("history", [])
    if mode == "fixed":
        capacity = [v for v in vs if v.cause == "capacity"]
        infeasible = [a for a, k in OUTPUT_KEYS.items() if (state.get(k) or {}).get("solver_status") == "INFEASIBLE"]
        if capacity or infeasible:
            reasons = [state[OUTPUT_KEYS[a]].get("reason") for a in infeasible if state[OUTPUT_KEYS[a]].get("reason")]
            return Review(verdict="escalate", violations=vs, reason="infeasible",
                          feedback=" ".join(reasons) + " Retrying cannot create capacity; a human must decide "
                                                       "(divert, open surge capacity, call in off-duty staff)."), 0
        if history and history[-1].get("hash") == decisions_hash(state):
            return Review(verdict="escalate", violations=vs, reason="no_progress",
                          feedback="The revised outputs are identical to the previous attempt."), 0
        plan = [v for v in vs if v.cause == "plan"]
        if plan:
            return Review(verdict="replan", violations=vs, target_agents=[v.subject for v in plan if v.subject],
                          feedback=rule_feedback(plan), reason=f"{len(plan)} plan violation(s)"), 0
        if vs:
            return Review(verdict="revise", violations=vs, target_agents=agents_with, feedback=rule_feedback(vs),
                          reason=f"{len(vs)} hard violation(s)"), 0
    elif vs:  # naive: every violation is treated as fixable and the LLM writes the feedback
        feedback, calls = _llm_feedback(state, vs)
        targets = agents_with or [v.subject for v in vs if v.cause == "plan" and v.subject]
        return Review(verdict="revise", violations=vs, target_agents=targets, feedback=feedback,
                      reason=f"{len(vs)} hard violation(s) (naive: assumed fixable)"), calls
    return Review(verdict="approve", reason="all hard checks passed"), 0


def reviewer_node(state: dict, config: RunnableConfig) -> dict:
    db = db_from(config)
    vs = hard_checks(db, state)
    review, calls = decide(state, vs)
    count = state.get("revision_count", 0) + (0 if review.verdict == "approve" else 1)
    attempt = len(state.get("history", [])) + 1
    entry = {
        "attempt": attempt, "verdict": review.verdict, "reason": review.reason, "feedback": review.feedback,
        "violations": [v.model_dump() for v in vs], "hash": decisions_hash(state),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "outputs": {k: state.get(k) for k in OUTPUT_KEYS.values() if state.get(k)},
    }
    update: dict = {"review": review, "revision_count": count, "history": [entry],
                    "constraints": updated_constraints(state, vs),
                    "llm_calls": state.get("llm_calls", 0) + calls}
    if review.verdict == "revise":
        update["pending_agents"] = [a for a in OPS_AGENTS if a in review.target_agents]
    route = route_after_review({**state, **update})
    update["status"] = "needs_human" if route == "human_review" else ("approved" if route == "analytics" else "running")
    update["trace"] = [{"agent": "reviewer",
                        "summary": f"Attempt {attempt}: {review.verdict.upper()} ({review.reason}); "
                                   f"revision_count={count}; next={route}"}]
    return update
