"""Helpers shared by every agent node."""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig
from sqlalchemy.orm import Session

# thread_id -> DB session of the request currently driving that run. Sessions are looked up
# here rather than placed in the graph config, so they never reach the checkpointer.
_RUN_SESSIONS: dict[str, Session] = {}


def bind_session(thread_id: str, db: Session) -> None:
    _RUN_SESSIONS[thread_id] = db


def release_session(thread_id: str) -> None:
    _RUN_SESSIONS.pop(thread_id, None)


def db_from(config: RunnableConfig) -> Session:
    return _RUN_SESSIONS[config["configurable"]["thread_id"]]


def finish(state: dict, agent: str, output_key: str, output: dict[str, Any], summary: str) -> dict:
    """Standard node return: pop the agent from the queue, count the attempt, add a trace line."""
    pending = [a for a in state.get("pending_agents", []) if a != agent]
    attempts = {**state.get("attempts", {}), agent: state.get("attempts", {}).get(agent, 0) + 1}
    return {output_key: output, "pending_agents": pending, "attempts": attempts,
            "trace": [{"agent": agent, "summary": summary}]}


def constraint_list(state: dict, agent: str, key: str) -> set[str]:
    return set(state.get("constraints", {}).get(agent, {}).get(key, []))
