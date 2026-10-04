"""AI agent workflow, scenarios and recommendation review."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from core.deps import ADMIN, ALL_ROLES, require_roles
from database.session import get_db
from langgraph_workflow.runner import resume_workflow, run_workflow
from models import Recommendation, User
from schemas import AgentQuery, AgentResume, RecommendationDecision, RecommendationOut
from services.actions import apply_recommendation
from simulation.hospital_simulator import SCENARIOS, HospitalSimulator

router = APIRouter(tags=["agent"])

ROLE_RECOMMENDATION_AGENTS = {"doctor": ("scheduling",), "staff_coordinator": ("staff",)}


@router.post("/agent/query", summary="Ask the LangGraph agents a question")
def agent_query(body: AgentQuery, db: Session = Depends(get_db), user: User = Depends(require_roles(*ALL_ROLES))) -> dict:
    return run_workflow(db, query=body.query, role=user.role)


@router.post("/agent/resume", summary="Approve or reject a run paused for human review (admin)")
def agent_resume(body: AgentResume, db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN))) -> dict:
    try:
        return resume_workflow(db, body.thread_id, body.action, body.note)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown or expired run (runs are kept in memory)") from None
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from None


# ---------------------------------------------------------------- scenarios
@router.get("/scenarios", summary="Built-in demo scenarios (admin)")
def list_scenarios(_: User = Depends(require_roles(*ADMIN))) -> list[dict]:
    return [{"id": s.id, "name": s.name, "description": s.description} for s in SCENARIOS.values()]


@router.post("/scenarios/{scenario_id}/run", summary="Apply a scenario, then run every agent (admin)")
def run_scenario(scenario_id: str, db: Session = Depends(get_db), user: User = Depends(require_roles(*ADMIN))) -> dict:
    if scenario_id not in SCENARIOS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown scenario '{scenario_id}'")
    sc = SCENARIOS[scenario_id]
    sim = HospitalSimulator(db)
    changes = sim.apply(scenario_id)  # resets the baseline, so the request session is replaced
    try:
        run = run_workflow(sim.db, query=f"Scenario '{sc.name}': summarise the situation and the recommended actions.",
                           role=user.role, mode="scenario", scenario_id=scenario_id, inject_fault=sc.inject_fault)
    finally:
        sim.db.close()
    return {"scenario": {"id": sc.id, "name": sc.name}, "changes": changes, "agent_run": run}


@router.post("/scenarios/reset", summary="Restore the seeded baseline (admin)")
def reset_scenarios(db: Session = Depends(get_db), _: User = Depends(require_roles(*ADMIN))) -> dict:
    db.close()
    HospitalSimulator.reset()
    return {"status": "reset"}


# ---------------------------------------------------------------- recommendations
@router.get("/recommendations", summary="Agent recommendations (filtered to the role's agents)")
def list_recommendations(status_filter: str | None = Query(None, alias="status"), limit: int = Query(50, ge=1, le=200),
                         db: Session = Depends(get_db), user: User = Depends(require_roles(*ALL_ROLES))) -> dict:
    q = select(Recommendation)
    if user.role in ROLE_RECOMMENDATION_AGENTS:
        q = q.where(Recommendation.agent.in_(ROLE_RECOMMENDATION_AGENTS[user.role]))
    if status_filter:
        q = q.where(Recommendation.status == status_filter)
    rows = db.scalars(q.order_by(Recommendation.created_at.desc()).limit(limit)).all()
    return {"items": [RecommendationOut.model_validate(r).model_dump(mode="json") for r in rows], "total": len(rows)}


@router.post("/recommendations/{rec_id}/decision", response_model=RecommendationOut,
             summary="Accept (and apply) or override a recommendation (admin)")
def decide_recommendation(rec_id: int, body: RecommendationDecision, db: Session = Depends(get_db),
                          user: User = Depends(require_roles(*ADMIN))) -> RecommendationOut:
    rec = db.get(Recommendation, rec_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Recommendation not found")
    if rec.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Recommendation already {rec.status}")
    if body.action == "override" and not body.note.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "An override needs a note explaining why")
    applied = apply_recommendation(db, rec.agent, rec.details) if body.action == "accept" else {}
    rec.status = "accepted" if body.action == "accept" else "overridden"
    rec.decided_by, rec.override_note = user.username, body.note or None
    if applied:
        rec.details = {**rec.details, "applied": applied, "applied_at": datetime.now().isoformat(timespec="seconds")}
    db.commit()
    return RecommendationOut.model_validate(rec)
