"""Human review node: pauses the graph with interrupt() until an administrator decides.

The reviewer has already set status="needs_human". The interrupt payload carries the best
outputs so far (attempt with the fewest violations), the unresolved violations, the attempt
history and a one-paragraph summary of why escalation happened. On resume
(`Command(resume={"action": ..., "note": ...})`) the node re-runs, interrupt() returns the
decision, and the status becomes human_approved or human_rejected.
"""

from __future__ import annotations

from langgraph.types import interrupt

from langgraph_workflow.reviewer import OUTPUT_KEYS
from langgraph_workflow.state import HumanDecision


def best_attempt(history: list[dict]) -> dict:
    """Fewest violations; ties go to the latest attempt."""
    return min(history, key=lambda h: (len(h["violations"]), -h["attempt"]))


def escalation_summary(state: dict) -> tuple[str, str]:
    review, n, cap = state["review"], state.get("revision_count", 0), state.get("max_revisions", 2)
    attempts = len(state.get("history", []))
    if review.verdict == "escalate" and review.reason == "infeasible":
        return "infeasible", (f"The reviewer escalated after {attempts} attempt(s) because the plan is infeasible "
                              f"with current resources. {review.feedback}")
    if review.verdict == "escalate":
        return "no_progress", (f"The reviewer escalated after {attempts} attempt(s): the latest revision was "
                               f"identical to the previous one, so retrying would not change anything.")
    return "cap", (f"The reviewer rejected the plan {n} times, reaching the revision cap of {cap}. Instead of "
                   f"looping again, the best plan so far and the unresolved issues are handed to an administrator. "
                   f"Latest feedback: {review.feedback[:400]}")


def human_review_node(state: dict) -> dict:
    best = best_attempt(state.get("history", []))
    reason, summary = escalation_summary(state)
    payload = {
        "reason": reason,
        "summary": summary,
        "unresolved_violations": [v.model_dump() for v in state["review"].violations],
        "best_attempt": best["attempt"],
        "best_outputs": best["outputs"],
        "revision_count": state.get("revision_count", 0),
    }
    raw = interrupt(payload)  # the graph pauses here until Command(resume=...)
    decision = raw if isinstance(raw, HumanDecision) else HumanDecision.model_validate(raw)

    approved = decision.action == "approve"
    update: dict = {
        "human_decision": decision,
        "escalation": payload,
        "status": "human_approved" if approved else "human_rejected",
        "trace": [{"agent": "human_review",
                   "summary": f"{decision.action.upper()} ({reason}) attempt {best['attempt']}"
                              + (f" - note: {decision.note}" if decision.note else "")}],
    }
    if approved:  # continue with the best outputs, not necessarily the latest
        for key in OUTPUT_KEYS.values():
            if key in best["outputs"]:
                update[key] = best["outputs"][key]
    return update
