"""Beds, staff and emergency operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from langchain_core.runnables import RunnableConfig
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agents.base import bind_session, release_session
from agents.emergency_agent import emergency_agent
from agents.resource_agent import plan_beds
from agents.staff_agent import plan_staff
from core.deps import ADMIN, ADMIN_COORDINATOR, ADMIN_DOCTOR, require_roles
from database.session import get_db
from models import Bed, EmergencyCase, Recommendation, Staff, User
from schemas import BedAllocateRequest, BedOut, EmergencyCaseOut, EmergencyCreate, RebalanceRequest, StaffOut
from services.actions import apply_bed_assignments, apply_staff_moves, reserve_beds
from services.hospital_state import ACTIVE_EMERGENCY, emergency_surge, get_now, staff_summary, ward_summary

router = APIRouter(tags=["operations"])


def _record(db: Session, agent: str, title: str, details: dict, status: str = "pending",
            decided_by: str | None = None) -> int:
    rec = Recommendation(agent=agent, title=title[:200], details=details, status=status, decided_by=decided_by)
    db.add(rec)
    db.commit()
    return rec.id


# ---------------------------------------------------------------- beds
@router.get("/beds", summary="Beds with occupancy (summary always covers the whole hospital)")
def list_beds(ward: str | None = None, status: str | None = None, limit: int = Query(500, ge=1, le=500),
              offset: int = Query(0, ge=0), db: Session = Depends(get_db),
              _: User = Depends(require_roles(*ADMIN_DOCTOR))) -> dict:
    q = select(Bed)
    if ward:
        q = q.where(Bed.ward == ward)
    if status:
        q = q.where(Bed.occupancy_status == status)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    beds = db.scalars(q.order_by(Bed.bed_id).limit(limit).offset(offset)).unique().all()
    items = [BedOut(id=b.id, bed_id=b.bed_id, ward=b.ward, bed_type=b.bed_type, occupancy_status=b.occupancy_status,
                    patient_id=b.patient_id, patient_name=b.patient.name if b.patient else None) for b in beds]
    summary = [{k: w[k] for k in ("ward", "total", "occupied", "available", "occupancy_pct")} for w in ward_summary(db)]
    return {"items": [i.model_dump() for i in items], "total": total, "summary": summary}


@router.post("/beds/allocate", summary="Run the OR-Tools bed optimiser and apply the assignments (admin)")
def allocate_beds(body: BedAllocateRequest, db: Session = Depends(get_db),
                  user: User = Depends(require_roles(*ADMIN))) -> dict:
    plan = plan_beds(db, body.patient_ids)
    apply_bed_assignments(db, plan.assignments)
    details = {"assignments": plan.assignments, "unassigned": plan.unassigned,
               "utilization_score": plan.utilization_score, "solver_status": plan.solver_status}
    rec_id = _record(db, "resource", f"Allocated {len(plan.assignments)} bed(s) (utilization {plan.utilization_score}%)",
                     details, status="accepted", decided_by=user.username)
    return {**details, "recommendation_id": rec_id}


# ---------------------------------------------------------------- staff
@router.get("/staff", summary="Staff and per-department workload (admin, coordinator)")
def list_staff(department: str | None = None, shift: str | None = None, limit: int = Query(500, ge=1, le=500),
               offset: int = Query(0, ge=0), db: Session = Depends(get_db),
               _: User = Depends(require_roles(*ADMIN_COORDINATOR))) -> dict:
    q = select(Staff)
    if department:
        q = q.where(Staff.department == department)
    if shift:
        q = q.where(Staff.shift == shift)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Staff.staff_id).limit(limit).offset(offset)).all()
    return {"items": [StaffOut.model_validate(s).model_dump() for s in rows], "total": total,
            "summary": staff_summary(db)}


@router.post("/staff/rebalance", summary="Propose (or apply) staff reallocation with OR-Tools")
def rebalance_staff(body: RebalanceRequest, db: Session = Depends(get_db),
                    user: User = Depends(require_roles(*ADMIN_COORDINATOR))) -> dict:
    plan = plan_staff(db)  # deterministic solver: applying reproduces the previewed plan
    if body.apply:
        apply_staff_moves(db, plan.moves)
    details = {"staff_reallocation": plan.staff_reallocation, "moves": plan.moves,
               "before": [{"department": r["department"], "load_ratio": r["load_ratio"]} for r in plan.before],
               "after": [{"department": r["department"], "load_ratio": r["load_ratio"]} for r in plan.after],
               "solver_status": plan.solver_status, "reason": plan.reason}
    rec_id = _record(db, "staff", f"{'Applied' if body.apply else 'Proposed'} {len(plan.moves)} staff move(s)", details,
                     status="accepted" if body.apply else "pending", decided_by=user.username if body.apply else None)
    return {**details, "applied": body.apply, "recommendation_id": rec_id}


# ---------------------------------------------------------------- emergency
@router.get("/emergency", summary="Emergency cases and surge status (admin)")
def list_emergencies(status: str = Query("active", pattern="^(active|all)$"), limit: int = Query(100, ge=1, le=500),
                     db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN))) -> dict:
    q = select(EmergencyCase)
    if status == "active":
        q = q.where(EmergencyCase.status.in_(ACTIVE_EMERGENCY))
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(EmergencyCase.arrival_time.desc()).limit(limit)).all()
    return {"items": [EmergencyCaseOut.model_validate(c).model_dump(mode="json") for c in rows], "total": total,
            "surge": emergency_surge(db)}


@router.post("/emergency", summary="Register incoming emergency cases and run the Emergency Response Agent")
def register_emergency(body: EmergencyCreate, db: Session = Depends(get_db),
                       user: User = Depends(require_roles(*ADMIN))) -> dict:
    now = get_now(db)
    base = db.scalar(select(func.count()).select_from(EmergencyCase)) or 0
    cases = [EmergencyCase(case_id=f"E{base + i + 1:04d}", severity=body.severity, department=body.department,
                           arrival_time=now, response_time=None, status="waiting") for i in range(body.count)]
    db.add_all(cases)
    db.commit()
    thread = f"emergency-{cases[0].case_id}"
    bind_session(thread, db)
    try:
        result = emergency_agent({"pending_agents": [], "attempts": {}},
                                 RunnableConfig(configurable={"thread_id": thread}))["emergency_status"]
    finally:
        release_session(thread)
    reserve_beds(db, result["reserved_beds"])
    rec_id = _record(db, "emergency", f"{result['priority_level']} priority: " + "; ".join(result["recommended_actions"][:2]),
                     result, status="accepted", decided_by=user.username)
    response = {k: result[k] for k in ("priority_level", "recommended_actions", "reserved_beds", "surge_detected")}
    return {"cases": [EmergencyCaseOut.model_validate(c).model_dump(mode="json") for c in cases],
            "response": response, "recommendation_id": rec_id}
