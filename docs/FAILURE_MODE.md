# Failure mode: a reviewer that cannot tell "badly done" from "impossible"

Everything below comes from real runs against the NVIDIA API catalog
(`nvidia/nemotron-3-super-120b-a12b`, thinking disabled) with the response cache **off**, so
every LLM call is counted. Full traces are in [`docs/runs/`](runs/). Each run resets the
database to the seeded baseline, applies the scenario, runs every agent, and, when the graph
pauses for human review, approves with the note *"Divert remaining critical cases to the
regional trauma network"*.

| Trace | Reviewer | Cap | Verdicts | Decision hash per attempt | LLM calls | Wall time* |
|---|---|---|---|---|---|---|
| [`mass_casualty_naive_cap2`](runs/mass_casualty_naive_cap2.txt) | naive | 2 | revise → revise → human | `53b4b0da…` ×2 | **3** | 20.0 s |
| [`mass_casualty_naive_cap4`](runs/mass_casualty_naive_cap4.txt) | naive | 4 | revise ×4 → human | `53b4b0da…` ×4 | **5** | 24.4 s |
| [`mass_casualty_fixed_cap2`](runs/mass_casualty_fixed_cap2.txt) | fixed | 2 | escalate → human | `53b4b0da…` ×1 | **1** | 16.1 s |
| [`icu_shortage_naive_cap2`](runs/icu_shortage_naive_cap2.txt) | naive | 2 | revise → revise → human | `81539da4…` ×2 | **3** | 20.5 s |
| [`icu_shortage_fixed_cap2`](runs/icu_shortage_fixed_cap2.txt) | fixed | 2 | escalate → human | `81539da4…` ×1 | **1** | 18.4 s |
| [`staff_shortage_fixed_cap2`](runs/staff_shortage_fixed_cap2.txt) | fixed | 2 | revise → approve | two different hashes | **1** | 16.5 s |

\* Wall time includes about 10 s of resetting the database to baseline. LLM call counts don't vary between runs; wall time does.

Reproduce (from `backend/`):

```bash
LLM_CACHE_ENABLED=false python scripts/run_scenario.py --scenario mass_casualty --mode naive --max-revisions 2 --auto-human approve
LLM_CACHE_ENABLED=false python scripts/run_scenario.py --scenario mass_casualty --mode fixed --max-revisions 2 --auto-human approve
```

## 1. What happened

**Mass Casualty Emergency** adds 16 emergency cases (8 critical) in 40 minutes plus 6 critical
trauma admissions. The ICU has 5 free beds. No allocation can satisfy the hard rules:
6 critical inpatients and 9 critical emergency cases all need ICU beds.

**Naive mode.** The Resource Agent beds 11 of 12 waiting patients and reports one critical patient
(P05001) it cannot place. The Emergency Agent reports an ICU shortfall of 9. The naive reviewer
sees 2 hard violations, treats them as fixable, and asks the LLM to write revision feedback.
The agents re-run their solvers on an unchanged hospital and produce the **same decisions**:

```
  review attempt 1: REVISE (2 hard violation(s) (naive: assumed fixable)) decision hash 53b4b0da4329904b
  review attempt 2: REVISE (2 hard violation(s) (naive: assumed fixable)) decision hash 53b4b0da4329904b
=== HUMAN REVIEW (graph paused at interrupt()) reason=cap
```

The loop stops only because `revision_count` reached `MAX_REVISIONS`. Raising the cap to 4 just
repeats the identical draft four times and spends 5 LLM calls instead of 3, with the same
outcome. The waste grows linearly with the cap, and the result never improves.

**Fixed mode.** The same first outputs reach the reviewer, which sees `solver_status ==
INFEASIBLE` (capacity violations) and escalates on review 1 without calling the LLM:

```
  review attempt 1: ESCALATE (infeasible) decision hash 53b4b0da4329904b
=== HUMAN REVIEW (graph paused at interrupt()) reason=infeasible
  ... 1 of 12 patients cannot be bedded: 6 critical patients need ICU beds and 5 ICU beds are free.
  9 critical emergency case(s) need ICU beds but only 0 ICU bed(s) remain free after inpatient
  allocation. Retrying cannot create capacity; a human must decide (divert, open surge capacity,
  call in off-duty staff).
```

The **ICU Capacity Shortage** scenario (1 free ICU bed, 4 new critical patients) shows exactly the
same pattern: naive gives `81539da4…` twice, 3 calls, and the cap; fixed escalates on the first
review with 1 call.

## 2. Root cause

The reviewer had one response to any violation: send the work back. It could not tell apart
two very different situations:

- **Badly executed:** a feasible plan done wrong. Retrying with the violation as a constraint
  fixes it. The Staff Shortage run shows this working: the first staffing plan moved S007 to a
  workload of 107 (> 100 cap); the reviewer turned that into "exclude S007", and attempt 2 was
  approved.
- **Impossible:** no assignment satisfies the hard constraints. The solvers are deterministic,
  so the same inputs give the same output, and a retry can never succeed.

The solvers already knew the plan was impossible (`INFEASIBLE`, with a reason). The naive reviewer
ignored that signal and treated the symptoms (unbedded patients, ICU shortfall) as defects.

## 3. Why this is dangerous in a hospital

- **Delay during an emergency.** Every pointless retry holds up the escalation. In the naive
  cap-4 run the administrator learns the ICU is physically full only after four identical
  rejections. In a real mass-casualty event, the time between "this is impossible" and
  "someone is diverting ambulances" is what matters.
- **Wasted capacity.** Free-tier credits and rate limits (about 40 requests/min) are spent on calls that
  cannot change the outcome: 3× the calls at cap 2, 5× at cap 4.
- **A false impression that the system is working.** The trace looks busy ("revise",
  "re-running allocation") while nothing changes.
- **The LLM's "fixes" push toward unsafe or out-of-scope actions.** Asked how to fix an
  impossible plan, the model invented remedies. From `mass_casualty_naive_cap4.txt`:
  > "Ensure all ICU bed assignments are prioritized by clinical urgency using a validated triage
  > score (e.g., SOFA or APACHE-II)"

  That is a clinical recommendation from an operations tool that must never make clinical
  decisions. The same feedback said the plan failed "despite available resources or insufficient
  capacity planning" (no ICU beds were free) and proposed moving "non-critical inpatients" out of an
  ICU that only holds critical patients.
  Here the agents are deterministic solvers and ignore free text. An LLM-driven agent that
  acted on this feedback could have done real harm.

## 4. The fix and its evidence

`REVIEWER_MODE=fixed` (the default) adds two checks *before* any retry decision, in
`backend/langgraph_workflow/reviewer.py::decide`:

1. **Infeasibility detection.** Any violation with `cause="capacity"`, or any agent output with
   `solver_status == "INFEASIBLE"`, means **escalate**, with the solvers' own explanation of the shortfall.
2. **No-progress detection.** If the decision hash (beds, staff moves, appointment slot, reserved
   beds, solver statuses) equals the previous attempt's, the verdict is **escalate**.

Each violation also records a `cause` (`execution` | `plan` | `capacity`), so the reviewer can
choose **revise** (the offending agent, with the violation turned into a solver constraint),
**replan** (back to the supervisor) or **escalate** (to a human). Revision feedback is generated
from the rules, so the LLM is never asked how to fix the impossible.

Evidence: in fixed mode both impossible scenarios escalate on the first review with a precise
shortfall, using 1 LLM call instead of 3 or 5. The fixable path still works: Staff Shortage goes
revise → approve with the over-cap move removed. Normal Operating Day and Monday Morning Rush are
approved first time.

## 5. Remaining limitations and other failure modes observed

**Limits of the fix**
- "Infeasible" is relative to the model. The solvers only know the beds and staff in the
  database. Real options (corridor beds, transfers, off-roster staff) are outside them, which is
  why the system escalates to a person instead of ending the run.
- The no-progress check catches exact repeats only. Two alternating drafts (A, B, A …) would pass
  it; the revision cap is the backstop.
- Runs paused for human review live in the API process's memory (in-memory checkpointer). A
  backend restart loses them. A Postgres checkpointer would fix this.
- The Staff Shortage fault injection is a demo mechanism to make the revise path visible, not
  something the real optimiser does.

**Other failure modes seen during development (all from real runs)**
1. **The report credited the reviewer's advice to the administrator.** In the first naive
   mass-casualty run ([`runs/dev/mass_casualty_naive_cap2_before_attribution_fix.txt`](runs/dev/mass_casualty_naive_cap2_before_attribution_fix.txt))
   the report said *"The administrator advises … reallocating non-critical ICU inpatients to
   step-down wards"*. The administrator's note only said to divert. The escalation summary
   passed to the Analytics Agent mixed the reviewer's LLM feedback in, unlabelled. Fix: the
   facts now carry only the administrator's own note, explicitly labelled, and the prompt says
   to quote nothing else as theirs. The re-run reports *"An administrator approved the escalated
   plan, stating: 'Divert remaining critical cases to the regional trauma network.'"*
2. **"Human approved" when no human was involved.** Early on, the analytics answer for an
   automatically approved run said *"human approved plan"*. The facts only said "verdict: approve".
   Fix: the facts state who approved (`the automated reviewer (no human involved)` vs an
   administrator).
3. **Misreading the staffing target.** The same answer called departments at 5.8 patients per
   staff member "understaffed", but the target is 6. Fix: the facts state the threshold explicitly.
4. **Baseline flagged as infeasible.** With an initial target of 4 patients per staff member, a
   *normal* day was escalated (`staff_shortfall`), because a morning shift of about 38 on-duty
   staff covers about 180 patients. Tuned to 6 patients per on-duty staff member. Genuine shortages
   still escalate.
5. **Ambiguous fact names lead to wrong claims.** Asked *"Why was a patient delayed?"*, the model
   said *"the Cardiology department had 26 appointments scheduled in that hour"*. The fact,
   named `hospital_appointments_that_hour`, was a hospital-wide count. Renamed to
   `appointments_that_hour_across_ALL_departments`; the answer now says *"26 appointments occurred
   across all departments at that hour"*. Lesson: in grounded generation, fact names are part of
   the prompt and must be unambiguous.
6. **Retired models still listed.** The brief's model (Llama 3.1 70B Instruct) and others return
   HTTP 410 while still appearing in the catalog listing. `services/nvidia_llm.py` sends one tiny
   probe request per model at startup and falls back
   (`nemotron-3-super-120b-a12b` → `nemotron-3-ultra-550b-a55b`); 404/410 are never retried.

**Not observed** (but handled): the model never returned invalid JSON in these runs, so the
corrective-retry path in `chat_json` has not been triggered live. No HTTP 429s occurred; runs
make 1–5 calls, well under the free-tier rate limit.
