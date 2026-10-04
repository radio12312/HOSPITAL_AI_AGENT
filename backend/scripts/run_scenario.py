"""Run a scenario through the agent workflow from the command line and print the trace.

    python scripts/run_scenario.py --scenario mass_casualty --mode naive --max-revisions 2
    python scripts/run_scenario.py --scenario staff_shortage --auto-human approve --save-trace ../docs/runs/x.txt

Run from backend/. The scenario resets the database to the seeded baseline first.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings  # noqa: E402
from database.session import SessionLocal  # noqa: E402
from langgraph_workflow.runner import resume_workflow, run_workflow  # noqa: E402
from services.nvidia_llm import LLMError, resolve_model  # noqa: E402
from simulation.hospital_simulator import SCENARIOS, HospitalSimulator  # noqa: E402


class Tee:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        print(text, flush=True)
        self.lines.append(text)


def show_run(out: Tee, r: dict) -> None:
    for t in r["trace"]:
        out(f"  > [{t['agent']}] {t['summary']}")
    for h in r["review"]["history"]:
        out(f"\n  review attempt {h['attempt']}: {h['verdict'].upper()} ({h['reason']}) decision hash {h['hash']}")
        for v in h["violations"]:
            out(f"    - [{v['agent']}/{v['rule']}/{v['cause']}] {v['detail']}")
        if h["feedback"]:
            out(f"    feedback: {h['feedback']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenario", required=True, choices=list(SCENARIOS))
    ap.add_argument("--mode", choices=["naive", "fixed"], default=settings.reviewer_mode)
    ap.add_argument("--max-revisions", type=int, default=settings.max_revisions)
    ap.add_argument("--auto-human", choices=["approve", "reject"], default=None)
    ap.add_argument("--human-note", default="")
    ap.add_argument("--save-trace", default=None)
    args = ap.parse_args()
    for s in (sys.stdout, sys.stderr):
        s.reconfigure(encoding="utf-8", errors="replace")

    out = Tee()
    try:
        model = resolve_model()
    except LLMError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    sc = SCENARIOS[args.scenario]
    out(f"scenario={sc.id} ({sc.name}) reviewer_mode={args.mode} max_revisions={args.max_revisions} model={model} "
        f"cache={'on' if settings.llm_cache_enabled else 'off'}")
    t0 = time.perf_counter()
    sim = HospitalSimulator(SessionLocal())
    changes = sim.apply(sc.id)
    out(f"changes: {json.dumps(changes)}\n")
    db = sim.db
    r = run_workflow(db, query=f"Scenario '{sc.name}': summarise the situation and the recommended actions.",
                     role="admin", mode="scenario", scenario_id=sc.id, inject_fault=sc.inject_fault,
                     reviewer_mode=args.mode, max_revisions=args.max_revisions)
    show_run(out, r)
    if r["status"] == "needs_human":
        i = r["interrupt"]
        out(f"\n=== HUMAN REVIEW (graph paused at interrupt()) reason={i['reason']}")
        out(f"  {i['summary']}")
        action = args.auto_human or ("approve" if input("  approve or reject? [a/r] ").lower().startswith("a")
                                     else "reject")
        note = args.human_note if args.auto_human else input("  note: ")
        out(f"  decision: {action}" + (f" (note: {note})" if note else ""))
        before = len(r["trace"])
        r = resume_workflow(db, r["thread_id"], action, note)
        for t in r["trace"][before:]:
            out(f"  > [{t['agent']}] {t['summary']}")
    if r.get("answer"):
        out("\n=== FINAL REPORT\n" + "\n".join("  " + line for line in r["answer"].splitlines()))
    out("\n=== SUMMARY")
    out(f"  status: {r['status']}")
    out(f"  verdicts: {' -> '.join(h['verdict'] for h in r['review']['history'])}")
    out(f"  revision_count: {r['review']['revision_count']}")
    out(f"  LLM API calls: {r['llm_calls']} (cache hits not counted)")
    out(f"  wall time: {time.perf_counter() - t0:.1f}s (includes resetting the database to baseline)")
    db.close()
    if args.save_trace:
        Path(args.save_trace).parent.mkdir(parents=True, exist_ok=True)
        Path(args.save_trace).write_text("\n".join(out.lines) + "\n", encoding="utf-8")
        print(f"trace saved to {args.save_trace}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
