"""Supervisor node: decides which agents a request needs, within the user's role.

Keyword routing handles the common questions with no LLM call; the LLM classifies only
questions that match no keyword. Scenario runs use every agent the role permits.
On a `replan` verdict the reviewer's missing agents are added and the selection re-runs.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from langgraph_workflow.state import OPS_AGENTS
from services.nvidia_llm import LLMError, chat_json

ROLE_AGENTS: dict[str, tuple[str, ...]] = {
    "admin": OPS_AGENTS,
    "doctor": ("scheduling",),
    "staff_coordinator": ("staff",),
}

KEYWORDS: dict[str, tuple[str, ...]] = {
    "scheduling": ("appointment", "schedule", "doctor", "slot", "wait", "delay", "queue", "consult"),
    "resource": ("bed", "icu", "ward", "occupan", "utiliz", "utilis", "equipment", "resource", "capacity",
                 "constrained", "overload"),
    "staff": ("staff", "nurse", "shift", "workload", "overload", "rebalanc", "roster"),
    "emergency": ("emergency", "surge", "critical", "casualty", "trauma", "alert", "ambulance"),
}
ANALYTICS_ONLY = ("predict", "forecast", "demand", "tomorrow", "trend", "why", "explain", "summar")


class RouteDecision(BaseModel):
    agents: list[str] = Field(default_factory=list)
    reason: str = ""


ROUTER_SYSTEM = """You route hospital operations questions to specialist agents.
Agents: scheduling (appointments, doctors, waiting times), resource (beds, wards, ICU, equipment),
staff (staffing, shifts, workload), emergency (surges, critical cases, emergency response).
Reply with ONLY JSON: {"agents": ["..."], "reason": "short reason"}. Use [] if the question
only needs forecasts or explanations of the current state."""


def select_agents(query: str, role: str, mode: str) -> tuple[list[str], str, int]:
    """Return (agents in canonical order, how they were chosen, llm_calls)."""
    allowed = ROLE_AGENTS.get(role, ())
    if mode == "scenario":
        return list(allowed), "scenario run: every agent permitted for the role", 0
    q = query.lower()
    hits = [a for a, kws in KEYWORDS.items() if any(k in q for k in kws)]
    calls, method = 0, "keyword routing"
    if not hits and not any(k in q for k in ANALYTICS_ONLY):
        try:
            decision, calls = chat_json(ROUTER_SYSTEM, f"QUESTION: {query}", RouteDecision, label="supervisor")
            hits, method = [a for a in decision.agents if a in OPS_AGENTS], f"LLM routing ({decision.reason})"
        except LLMError:
            hits, method = list(allowed), "LLM unavailable: all permitted agents"
    chosen = [a for a in OPS_AGENTS if a in hits and a in allowed]
    dropped = [a for a in hits if a not in allowed]
    if dropped:
        method += f"; not permitted for {role}: {', '.join(dropped)}"
    return chosen, method, calls


def supervisor_node(state: dict) -> dict:
    review = state.get("review")
    if review is not None and review.verdict == "replan":
        allowed = ROLE_AGENTS.get(state.get("user_role", "admin"), ())
        selected = [a for a in OPS_AGENTS if a in set(state.get("selected_agents", [])) | set(review.target_agents)
                    and a in allowed]
        return {"selected_agents": selected, "pending_agents": list(selected),
                "trace": [{"agent": "supervisor", "summary": f"Replan: added {', '.join(review.target_agents)}; "
                                                              f"re-running {', '.join(selected)}"}]}
    agents, method, calls = select_agents(state.get("query", ""), state.get("user_role", "admin"),
                                          state.get("mode", "query"))
    summary = f"Routed to {', '.join(agents) or 'analytics only'} ({method})"
    return {"selected_agents": agents, "pending_agents": list(agents), "status": "running",
            "llm_calls": state.get("llm_calls", 0) + calls, "trace": [{"agent": "supervisor", "summary": summary}]}
