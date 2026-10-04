"""Runs the compiled graph for API requests and shapes the response.

One compiled graph per process with an in-memory checkpointer; every run gets its own
thread_id, which is what `POST /agent/resume` uses to continue a paused run.
"""

from __future__ import annotations

import uuid
from typing import Any

from langgraph.types import Command
from sqlalchemy.orm import Session

from agents.base import bind_session, release_session
from core.config import settings
from core.logging import get_logger
from langgraph_workflow.graph import build_graph
from langgraph_workflow.reviewer import OUTPUT_KEYS
from langgraph_workflow.state import HumanDecision
from models import Recommendation
from services.nvidia_llm import model_name

log = get_logger("workflow")
GRAPH = build_graph()

OUTPUT_NAMES = {v: k for k, v in OUTPUT_KEYS.items()}  # state key -> agent name


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}, "recursion_limit": 60}


def _persist_recommendations(db: Session, state: dict, thread_id: str) -> list[int]:
    ids = []
    for rec in state.get("recommendations") or []:
        row = Recommendation(agent=rec["agent"], title=rec["title"][:200], details=rec["details"],
                             thread_id=thread_id)
        db.add(row)
        db.flush()
        ids.append(row.id)
    db.commit()
    return ids


def _response(db: Session, thread_id: str) -> dict[str, Any]:
    snap = GRAPH.get_state(_config(thread_id))
    state = snap.values
    interrupts = [i.value for t in snap.tasks for i in t.interrupts]
    status = "needs_human" if interrupts else ("rejected" if state.get("status") == "human_rejected" else "completed")
    review = state.get("review")
    outputs = {OUTPUT_NAMES[k]: state[k] for k in OUTPUT_NAMES if state.get(k)}
    if state.get("answer"):
        outputs["analytics"] = {"summary": state["answer"]}
    rec_ids = []
    if status == "completed" and state.get("recommendations"):
        rec_ids = _persist_recommendations(db, state, thread_id)
        GRAPH.update_state(_config(thread_id), {"recommendations": []})  # persist once
    return {
        "status": status,
        "thread_id": thread_id,
        "answer": state.get("answer", "") if status == "completed" else "",
        "agents_used": [t["agent"] for t in state.get("trace", [])
                        if t["agent"] in OUTPUT_KEYS or t["agent"] == "analytics"],
        "outputs": outputs,
        "trace": state.get("trace", []),
        "llm_calls": state.get("llm_calls", 0),
        "model": model_name(),
        "review": {
            "verdict": review.verdict if review else None,
            "revision_count": state.get("revision_count", 0),
            "violations": [v.model_dump() for v in review.violations] if review else [],
            "history": [{k: h[k] for k in ("attempt", "verdict", "reason", "feedback", "violations", "hash")}
                        for h in state.get("history", [])],
        },
        "interrupt": interrupts[0] if interrupts else None,
        "recommendation_ids": rec_ids,
    }


def run_workflow(db: Session, *, query: str, role: str, mode: str = "query", scenario_id: str | None = None,
                 inject_fault: bool = False, patient_info: dict | None = None,
                 reviewer_mode: str | None = None, max_revisions: int | None = None) -> dict[str, Any]:
    thread_id = str(uuid.uuid4())
    initial = {
        "query": query, "user_role": role, "mode": mode, "scenario_id": scenario_id,
        "inject_fault": inject_fault, "patient_info": patient_info or {},
        "reviewer_mode": reviewer_mode or settings.reviewer_mode,
        "max_revisions": max_revisions or settings.max_revisions,
        "constraints": {}, "attempts": {}, "review": None, "revision_count": 0, "history": [],
        "human_decision": None, "escalation": None, "status": "running", "llm_calls": 0, "trace": [],
    }
    bind_session(thread_id, db)
    try:
        GRAPH.invoke(initial, _config(thread_id))
        result = _response(db, thread_id)
    finally:
        release_session(thread_id)
    log.info("Run %s: %s after %d review(s), %d LLM call(s)", thread_id[:8], result["status"],
             len(result["review"]["history"]), result["llm_calls"])
    return result


def resume_workflow(db: Session, thread_id: str, action: str, note: str = "") -> dict[str, Any]:
    snap = GRAPH.get_state(_config(thread_id))
    if not snap.values:
        raise KeyError("unknown thread_id")
    if not any(t.interrupts for t in snap.tasks):
        raise ValueError("this run is not waiting for human review")
    bind_session(thread_id, db)
    try:
        GRAPH.invoke(Command(resume=HumanDecision(action=action, note=note).model_dump()), _config(thread_id))
        return _response(db, thread_id)
    finally:
        release_session(thread_id)
