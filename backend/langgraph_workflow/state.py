"""Typed state schema for the hospital workflow graph.

`HospitalWorkflowState` is the TypedDict LangGraph passes between nodes. Every field documents
who writes it and who reads it. `history` and `trace` use an `operator.add` reducer, so they
are append-only audit logs.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, Field

AgentName = Literal["scheduling", "resource", "staff", "emergency"]
OPS_AGENTS: tuple[AgentName, ...] = ("scheduling", "resource", "staff", "emergency")  # canonical order

Status = Literal["running", "approved", "needs_human", "human_approved", "human_rejected"]
Verdict = Literal["approve", "revise", "replan", "escalate"]


class Violation(BaseModel):
    agent: str
    rule: str
    detail: str
    subject: str | None = None  # bed / staff / doctor id the agent can act on
    # Drives the verdict in "fixed" mode: execution -> revise, plan -> replan, capacity -> escalate
    cause: Literal["execution", "plan", "capacity"] = "execution"


class Review(BaseModel):
    verdict: Verdict
    violations: list[Violation] = Field(default_factory=list)
    target_agents: list[str] = Field(default_factory=list)  # agents to re-run on revise
    feedback: str = ""
    reason: str = ""  # one line explaining the verdict


class HumanDecision(BaseModel):
    action: Literal["approve", "reject"]
    note: str = ""


class HospitalWorkflowState(TypedDict, total=False):
    # ---- inputs (written by the runner at START) ----
    query: str                      # administrator question; read by supervisor, analytics
    user_role: str                  # admin | doctor | staff_coordinator; read by supervisor (RBAC routing)
    mode: Literal["query", "scenario"]  # scenario = run every permitted agent; read by supervisor
    scenario_id: str | None         # which scenario triggered the run; read by analytics
    inject_fault: bool              # demo flag: first staff plan breaks the workload cap; read by staff agent
    reviewer_mode: Literal["naive", "fixed"]  # read by reviewer (failure-mode study)
    max_revisions: int              # rejection cap; read by route_after_review
    patient_info: dict[str, Any]    # optional new-patient/appointment request; read by scheduling agent

    # ---- supervisor ----
    selected_agents: list[str]      # written by supervisor; read by reviewer (missing-agent check), runner
    pending_agents: list[str]       # queue of agents still to run; written by supervisor/agents/reviewer, read by routing

    # ---- agent outputs (the spec's state fields) ----
    appointment_info: dict[str, Any]   # written by scheduling agent; read by reviewer, analytics
    resource_status: dict[str, Any]    # written by resource agent; read by emergency agent, reviewer, analytics
    staff_status: dict[str, Any]       # written by staff agent; read by reviewer, analytics
    emergency_status: dict[str, Any]   # written by emergency agent; read by reviewer, analytics
    recommendations: list[dict[str, Any]]  # written by analytics (one per agent output); read by runner -> DB

    # ---- review loop ----
    constraints: dict[str, dict[str, list[str]]]  # reviewer feedback as solver constraints per agent; read by agents
    attempts: dict[str, int]        # runs per agent; written by agents; read by staff agent (fault injection)
    review: Review | None           # written by reviewer; read by routing, supervisor (replan), human_review
    revision_count: int             # +1 on every rejection, written by reviewer; read by route_after_review
    history: Annotated[list[dict[str, Any]], operator.add]  # every review (append-only); read by human_review, API
    human_decision: HumanDecision | None  # written by human_review on resume; read by route_after_human, analytics
    escalation: dict[str, Any] | None     # interrupt payload, written by human_review; read by API, analytics
    status: Status                  # written by reviewer / human_review / analytics; read by API

    # ---- output ----
    answer: str                     # written by analytics; read by API
    llm_calls: int                  # real API calls this run (cache hits excluded); every LLM node adds to it
    trace: Annotated[list[dict[str, str]], operator.add]  # {agent, summary} per step (append-only); read by API/UI
