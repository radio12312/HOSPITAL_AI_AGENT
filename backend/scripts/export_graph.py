"""Write docs/graph.mmd from the compiled LangGraph so the README diagram matches the code.

    python scripts/export_graph.py      (run from backend/)
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from langgraph_workflow.graph import build_graph  # noqa: E402

# Labels for the conditional edges (structure still comes from draw_mermaid()).
LABELS = {
    "reviewer -.-> analytics;": "reviewer -. &nbsp;approve&nbsp; .-> analytics;",
    "reviewer -.-> human_review;": "reviewer -. &nbsp;escalate OR revision_count ≥ cap&nbsp; .-> human_review;",
    "reviewer -.-> supervisor;": "reviewer -. &nbsp;replan&nbsp; .-> supervisor;",
    **{f"reviewer -.-> {a};": f"reviewer -. &nbsp;revise&nbsp; .-> {a};" for a in ("scheduling", "resource", "staff", "emergency")},
    "human_review -.-> analytics;": "human_review -. &nbsp;human approves&nbsp; .-> analytics;",
    "human_review -. &nbsp;end&nbsp; .-> __end__;": "human_review -. &nbsp;human rejects&nbsp; .-> __end__;",
}


def mermaid() -> str:
    text = build_graph().get_graph().draw_mermaid()
    for raw, labelled in LABELS.items():
        text = text.replace(raw, labelled)
    return text


def main() -> None:
    out = BACKEND.parent / "docs" / "graph.mmd"
    out.parent.mkdir(exist_ok=True)
    out.write_text(mermaid(), encoding="utf-8")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
