"""Builds and compiles the hospital workflow StateGraph.

    START -> supervisor --route_next--> scheduling -> resource -> staff -> emergency (only the selected ones)
          each agent --route_next--> next selected agent | reviewer | analytics
    reviewer --route_after_review--> analytics | human_review | supervisor | <agent to revise>
    human_review --route_after_human--> analytics | END
    analytics -> END
"""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph

from agents.analytics_agent import analytics_agent
from agents.emergency_agent import emergency_agent
from agents.resource_agent import resource_agent
from agents.scheduling_agent import scheduling_agent
from agents.staff_agent import staff_agent
from langgraph_workflow.human_review import human_review_node
from langgraph_workflow.reviewer import reviewer_node
from langgraph_workflow.routing import route_after_human, route_after_review, route_next
from langgraph_workflow.state import HospitalWorkflowState
from langgraph_workflow.supervisor import supervisor_node

AGENT_NODES = {"scheduling": scheduling_agent, "resource": resource_agent, "staff": staff_agent,
               "emergency": emergency_agent}
ORDER = list(AGENT_NODES)  # canonical order; the pending queue always follows it


def next_map(after: str | None) -> dict[str, str]:
    """Exact routing targets: only agents later in the canonical order, then the reviewer.

    The supervisor may also go straight to analytics (questions that need no operational agent).
    """
    later = ORDER if after is None else ORDER[ORDER.index(after) + 1:]
    targets = [*later, "analytics"] if after is None else [*later, "reviewer"]
    return {t: t for t in targets}


def _serializer() -> JsonPlusSerializer:
    # Explicitly allow our Pydantic state models in checkpoints.
    return JsonPlusSerializer(allowed_msgpack_modules=[("langgraph_workflow.state", n)
                                                       for n in ("Review", "Violation", "HumanDecision")])


def build_graph(checkpointer=None):
    g = StateGraph(HospitalWorkflowState)
    g.add_node("supervisor", supervisor_node)
    for name, fn in AGENT_NODES.items():
        g.add_node(name, fn)
    g.add_node("reviewer", reviewer_node)
    g.add_node("human_review", human_review_node)
    g.add_node("analytics", analytics_agent)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", route_next, next_map(None))
    for name in AGENT_NODES:
        g.add_conditional_edges(name, route_next, next_map(name))
    g.add_conditional_edges("reviewer", route_after_review,
                            {"analytics": "analytics", "human_review": "human_review", "supervisor": "supervisor",
                             **{name: name for name in AGENT_NODES}})
    g.add_conditional_edges("human_review", route_after_human, {"analytics": "analytics", "end": END})
    g.add_edge("analytics", END)
    # A checkpointer is required for interrupt()/resume in human_review.
    return g.compile(checkpointer=checkpointer or InMemorySaver(serde=_serializer()))
