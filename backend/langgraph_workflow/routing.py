"""Conditional-edge routing functions (pure functions of the state)."""

from __future__ import annotations

from typing import Literal

DEFAULT_MAX_REVISIONS = 2

NextStep = Literal["scheduling", "resource", "staff", "emergency", "reviewer", "analytics"]
ReviewRoute = Literal["analytics", "human_review", "supervisor", "scheduling", "resource", "staff", "emergency"]


def route_next(state: dict) -> NextStep:
    """After the supervisor and after every operational agent: run the next queued agent.

    When the queue is empty, go to the reviewer if any operational agent ran; questions that
    only need forecasts or explanations go straight to the analytics agent.
    """
    pending = state.get("pending_agents") or []
    if pending:
        return pending[0]
    # Queue empty: review whatever ran; with no operational agent selected, answer directly.
    return "reviewer" if state.get("selected_agents") else "analytics"


def route_after_review(state: dict) -> ReviewRoute:
    """Decide where the graph goes after the reviewer. Order matters:

      1. approve  -> analytics
      2. escalate -> human_review (always wins, whatever the counter says)
      3. cap reached (revision_count >= max_revisions) -> human_review. The reviewer has
         already incremented revision_count for this rejection, so with max_revisions=2
         rejection #1 retries and rejection #2 escalates. There is never a third attempt.
      4. replan -> supervisor (the agent selection was wrong)
      5. revise -> the first agent the reviewer flagged (its violations become constraints)
    """
    review = state.get("review")
    if review is None:
        raise ValueError("route_after_review called before the reviewer wrote a review")
    if review.verdict == "approve":
        return "analytics"
    if review.verdict == "escalate":
        return "human_review"
    if state.get("revision_count", 0) >= state.get("max_revisions", DEFAULT_MAX_REVISIONS):
        return "human_review"
    if review.verdict == "replan":
        return "supervisor"
    pending = state.get("pending_agents") or review.target_agents
    return pending[0] if pending else "analytics"


def route_after_human(state: dict) -> Literal["analytics", "end"]:
    decision = state.get("human_decision")
    return "analytics" if decision is not None and decision.action == "approve" else "end"
