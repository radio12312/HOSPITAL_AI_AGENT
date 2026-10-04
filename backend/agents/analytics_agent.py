"""Agent 5 - Analytics Agent (NVIDIA NIM).

Explains the other agents' decisions and answers administrator questions in plain language,
grounded only in facts gathered from the live state, the agents' outputs and the ML forecasts.
Also turns each agent output into a reviewable recommendation.
"""

from __future__ import annotations

import json
from datetime import timedelta

import pandas as pd

from langchain_core.runnables import RunnableConfig
from sqlalchemy import select

from agents.base import db_from
from core.constants import DEPARTMENTS, TARGET_PATIENTS_PER_STAFF
from ml.patient_demand_predictor import PatientDemandPredictor
from models import Appointment, Patient
from services.hospital_state import (
    bed_totals, day_bounds, emergency_surge, get_now, staff_summary, ward_summary,
)
from services.nvidia_llm import LLMError, chat

SYSTEM = """You are the analytics assistant of a hospital operations decision-support system.
You explain operational decisions (beds, staffing, scheduling, emergencies) to hospital
administrators. This is not clinical advice: never diagnose or recommend treatment.

Rules:
- Use ONLY the facts in the FACTS block. Never invent numbers, names, beds or times.
- Answer the question directly first, then give the key reasons with the actual numbers.
- If a human approved an escalated plan, say so, quote only the administrator_note as the
  administrator's words, and list the unresolved issues.
- Be concise: at most about 180 words, short paragraphs or bullet points."""


def demand_forecast(db, days: int = 7) -> list[dict]:
    """XGBoost admissions forecast for the next `days` days from the hospital clock."""
    now = get_now(db)
    start, _ = day_bounds(now)
    since = start - timedelta(days=7)
    rows = db.execute(select(Patient.admission_date, Patient.department)
                      .where(Patient.admission_date >= since, Patient.admission_date < start)).all()
    hist = pd.DataFrame(rows, columns=["admission_date", "department"])
    if hist.empty:
        hist = pd.DataFrame({"admission_date": [since], "department": [DEPARTMENTS[0]]})
    hist["date"] = pd.to_datetime(hist["admission_date"]).dt.normalize()
    daily = (hist.groupby(["date", "department"]).size().rename("admissions")
             .reindex(pd.MultiIndex.from_product([pd.date_range(since, start - timedelta(days=1)), DEPARTMENTS],
                                                 names=["date", "department"]), fill_value=0).reset_index())
    try:
        return PatientDemandPredictor().forecast(daily, (start + timedelta(days=1)).date(), days)
    except FileNotFoundError:
        return []


def most_delayed_today(db) -> dict | None:
    now = get_now(db)
    start, end = day_bounds(now)
    appt = db.scalar(select(Appointment).where(Appointment.appointment_time >= start,
                                               Appointment.appointment_time < end)
                     .order_by(Appointment.wait_time.desc()).limit(1))
    if not appt:
        return None
    same_doc = db.scalars(select(Appointment).where(Appointment.doctor_id == appt.doctor_id,
                                                    Appointment.appointment_time >= start,
                                                    Appointment.appointment_time < end)).all()
    same_hour = db.scalars(select(Appointment).where(Appointment.appointment_time >= appt.appointment_time.replace(minute=0),
                                                     Appointment.appointment_time < appt.appointment_time.replace(minute=0) + timedelta(hours=1))).all()
    return {"appointment_id": appt.appointment_id, "patient_id": appt.patient_id, "patient": appt.patient.name,
            "doctor": appt.doctor.name, "department": appt.doctor.specialization,
            "time": appt.appointment_time.strftime("%H:%M"), "wait_min": appt.wait_time,
            "doctor_appointments_today": len(same_doc), "doctor_daily_capacity": appt.doctor.daily_capacity,
            "appointments_that_hour_across_ALL_departments": len(same_hour)}


def build_recommendations(state: dict) -> list[dict]:
    recs = []
    if (a := state.get("appointment_info")) and a.get("doctor"):
        recs.append({"agent": "scheduling", "title": f"Book {a['department']} patient with {a['doctor']} at "
                     f"{a['recommended_slot']} (wait {a['predicted_wait_time']})", "details": a})
    if (r := state.get("resource_status")) and r.get("assignments"):
        recs.append({"agent": "resource", "title": f"Allocate {len(r['assignments'])} bed(s) "
                     f"(utilization {r['utilization_score']}%)", "details": r})
    if (s := state.get("staff_status")) and s.get("moves"):
        recs.append({"agent": "staff", "title": f"Reassign {len(s['moves'])} staff member(s) across "
                     f"{len(s['staff_reallocation'])} department pair(s)", "details": s})
    if (e := state.get("emergency_status")) and e.get("priority_level") not in (None, "Normal"):
        recs.append({"agent": "emergency", "title": f"{e['priority_level']} priority: "
                     + "; ".join(e["recommended_actions"][:2]), "details": e})
    return recs


def _compact(output: dict | None, drop: tuple[str, ...] = ()) -> dict | None:
    if not output:
        return None
    return {k: v for k, v in output.items() if k not in drop and v not in (None, [], {})}


def build_facts(db, state: dict) -> dict:
    now = get_now(db)
    q = (state.get("query") or "").lower()
    facts: dict = {
        "hospital_time": now.strftime("%a %d %b %Y %H:%M"),
        "beds": bed_totals(db),
        "wards": [{k: w[k] for k in ("ward", "occupied", "available", "occupancy_pct")} for w in ward_summary(db)],
        "emergency": emergency_surge(db),
    }
    if any(k in q for k in ("staff", "overload", "workload", "nurse", "shift")) or state.get("staff_status"):
        facts["staffing_target"] = (f"a department is understaffed only if patients per on-duty staff member "
                                    f"exceeds {TARGET_PATIENTS_PER_STAFF:g}")
        facts["staffing_now"] = [{k: s[k] for k in ("department", "on_duty", "patient_load", "load_ratio", "avg_workload")}
                                 for s in staff_summary(db)]
    if any(k in q for k in ("predict", "forecast", "demand", "tomorrow", "next week")) or state.get("mode") == "scenario":
        fc = demand_forecast(db, 7)
        facts["admissions_forecast_next_7_days"] = [{"date": f["date"], "expected": f["expected_admissions"]} for f in fc]
        if fc:
            top = sorted(fc[0]["by_department"].items(), key=lambda kv: -kv[1])[:3]
            facts["tomorrow_busiest_departments"] = dict(top)
    if any(k in q for k in ("delay", "wait", "late")):
        facts["most_delayed_appointment_today"] = most_delayed_today(db)
    facts["agent_outputs"] = {
        "scheduling": _compact(state.get("appointment_info")),
        "resource": _compact(state.get("resource_status"), ("ward_utilization", "equipment")),
        "staff": _compact(state.get("staff_status"), ("before",)),
        "emergency": _compact(state.get("emergency_status"), ("surge",)),
    }
    facts["agent_outputs"] = {k: v for k, v in facts["agent_outputs"].items() if v}
    if state.get("status") == "human_approved" and state.get("human_decision"):
        facts["approval"] = {"approved_by": "an administrator, after the automated reviewer escalated",
                             "administrator_note (the ONLY words from the administrator)": state["human_decision"].note,
                             "escalation_reason_code": (state.get("escalation") or {}).get("reason"),
                             "unresolved_issues": [v.detail for v in state["review"].violations][:8]}
    elif state.get("review"):
        facts["approval"] = {"approved_by": "the automated reviewer (no human involved)",
                             "revisions_needed": state.get("revision_count", 0)}
    return facts


def fallback_answer(facts: dict) -> str:
    b = facts["beds"]
    lines = [f"Bed occupancy is {b['occupancy_pct']}% (ICU {b['icu_occupancy_pct']}%, {b['icu_free']} ICU beds free)."]
    busiest = max(facts["wards"], key=lambda w: w["occupancy_pct"])
    lines.append(f"Most constrained ward: {busiest['ward']} at {busiest['occupancy_pct']}%.")
    e = facts["emergency"]
    lines.append(f"Emergency: {e['active_cases']} active cases, {e['critical_cases']} critical"
                 + (" - surge detected." if e["surge_detected"] else "."))
    for agent, out in facts.get("agent_outputs", {}).items():
        lines.append(f"{agent.title()} agent: {json.dumps(out, default=str)[:240]}")
    return "\n".join(lines) + "\n\n(The language model was unavailable, so this is a facts-only summary.)"


def analytics_agent(state: dict, config: RunnableConfig) -> dict:
    db = db_from(config)
    facts = build_facts(db, state)
    question = state.get("query") or "Summarise the current hospital situation and the agents' recommendations."
    user = f"QUESTION: {question}\n\nFACTS:\n{json.dumps(facts, default=str, indent=1)}"
    calls = 0
    try:
        res = chat(SYSTEM, user, label="analytics")
        answer, calls = res.text, res.api_calls
    except LLMError as e:
        answer = fallback_answer(facts)
        state_note = f"LLM unavailable ({e}); facts-only answer"
    else:
        state_note = f"Answered with {res.model}" + (" (cached)" if res.cache_hit else "")
    status = state.get("status")
    return {
        "answer": answer,
        "recommendations": build_recommendations(state),
        "status": "human_approved" if status == "human_approved" else "approved",
        "llm_calls": state.get("llm_calls", 0) + calls,
        "trace": [{"agent": "analytics", "summary": state_note}],
    }

