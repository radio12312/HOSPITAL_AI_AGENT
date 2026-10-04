# API Reference

Base URL: `http://localhost:8000` when running the backend directly. The frontend calls the API
through `/api`, which the Vite dev server and the production nginx container both proxy to the
backend with the `/api` prefix removed (`/api/beds` → `/beds`).

Interactive OpenAPI docs are served by FastAPI at `/docs` (Swagger UI) and `/redoc`.

## Conventions

- JSON in, JSON out. Timestamps are ISO-8601 strings (`2026-10-04T09:30:00`), dates are `YYYY-MM-DD`.
- Every endpoint except `POST /auth/login` and `GET /health` requires
  `Authorization: Bearer <access_token>`.
- Errors return `{"detail": "<message>"}` with status `400` (bad input), `401` (missing/expired
  token → client logs out), `403` (role not allowed), `404`, `422` (validation) or `503`
  (LLM unavailable; agent endpoints still return deterministic results where possible).
- List endpoints return `{"items": [...], "total": <int>}` and accept `limit` (default 50, max 500)
  and `offset` (default 0).

## Roles

| Role | Value | Can access |
|---|---|---|
| Admin | `admin` | Everything, including analytics, scenarios, bed allocation, emergency intake and recommendation overrides |
| Doctor | `doctor` | Dashboard, own appointments, assigned patients, beds (read), schedule suggestions, AI assistant (scheduling questions) |
| Staff Coordinator | `staff_coordinator` | Dashboard, staff workloads, shift rebalancing, staffing recommendations, AI assistant (staffing questions) |

Demo accounts created by `seed_data.py`: `admin / admin123`, `doctor / doctor123`,
`coordinator / coord123`. Change them for any real deployment.

---

## Auth

### `POST /auth/login`
Request: `{"username": "admin", "password": "admin123"}`

Response `200`:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": {"id": 1, "username": "admin", "email": "admin@hospital.local", "role": "admin", "doctor_id": null}
}
```
`doctor_id` is set (e.g. `"D001"`) for users with role `doctor`.

### `GET /auth/me`
Returns the `user` object above.

---

## Dashboard

### `GET /dashboard` (all roles)
```json
{
  "generated_at": "2026-10-04T09:30:00",
  "kpis": {
    "admissions_today": 21,
    "bed_occupancy_pct": 81.5,
    "icu_occupancy_pct": 86.7,
    "staff_on_duty": 64,
    "staff_total": 100,
    "active_emergencies": 7,
    "critical_emergencies": 2,
    "avg_predicted_wait_min": 18.4,
    "resource_utilization_pct": 77.2
  },
  "admissions_trend": [{"date": "2026-09-21", "admissions": 18}],
  "demand_forecast": [{"date": "2026-10-05", "expected_admissions": 22.4}],
  "occupancy_by_ward": [{"ward": "ICU", "total": 30, "occupied": 26, "available": 4, "occupancy_pct": 86.7}],
  "staff_by_department": [{"department": "Cardiology", "on_duty": 9, "total": 12, "avg_workload": 72.5}],
  "wait_time_by_department": [{"department": "Cardiology", "predicted_wait_min": 24.1}],
  "emergency_alerts": [{"case_id": "E0991", "severity": "critical", "department": "Emergency", "arrival_time": "2026-10-04T02:14:00", "status": "waiting"}],
  "equipment_utilization": [{"type": "Ventilator", "total": 20, "in_use": 15, "utilization_pct": 75.0}],
  "recent_recommendations": [Recommendation]
}
```
`admissions_trend` covers the last 14 days, `demand_forecast` the next 7 days (XGBoost).

---

## Patients

### `GET /patients` (admin: all; doctor: patients with an appointment with them)
Query: `search` (name or patient_id), `department`, `status` = `admitted` | `discharged` | `all`
(default `admitted`), `limit`, `offset`.

`Patient`:
```json
{
  "id": 12, "patient_id": "P00012", "name": "Jane Doe", "age": 67, "gender": "Female",
  "department": "Cardiology", "severity_score": 8.2,
  "admission_date": "2026-10-02T11:20:00", "discharge_date": null,
  "treatment_duration": 6, "bed_id": "CARD-07"
}
```
`severity_score` is 1.0–10.0 (≥ 8 = critical). `treatment_duration` is in days.

### `POST /patients` (admin)
Request: `{"name": "Jane Doe", "age": 67, "gender": "Female", "department": "Cardiology", "severity_score": 8.2}`
(`treatment_duration` optional; estimated from severity when omitted). Admits the patient now.
Response `201`: `Patient`.

---

## Doctors

### `GET /doctors` (all roles)
Query: `department`. Response: `{"items": [Doctor], "total": n}`
```json
{"id": 1, "doctor_id": "D001", "name": "Dr. Alex Smith", "specialization": "Cardiology",
 "experience_years": 14, "daily_capacity": 16, "availability_status": "available", "appointments_today": 11}
```
`availability_status`: `available` | `busy` | `off_duty`.

---

## Appointments

### `GET /appointments` (admin: all; doctor: own)
Query: `date` (default today), `doctor_id`, `status`, `limit`, `offset`.

`Appointment`:
```json
{
  "id": 501, "appointment_id": "A000501", "patient_id": "P00012", "patient_name": "Jane Doe",
  "doctor_id": "D001", "doctor_name": "Dr. Alex Smith", "department": "Cardiology",
  "appointment_time": "2026-10-04T10:30:00", "consultation_duration": 20, "wait_time": 15,
  "status": "scheduled"
}
```
`status`: `scheduled` | `completed` | `cancelled` | `no_show`. Durations/waits are minutes.

### `POST /appointments` (admin, doctor)
Request: `{"patient_id": "P00012", "department": "Cardiology", "doctor_id": null, "preferred_time": null}`
Missing `doctor_id` / `preferred_time` are filled in by the Scheduling Agent.

Response `201`:
```json
{
  "appointment": Appointment,
  "suggestion": {"doctor": "Dr. Alex Smith", "doctor_id": "D001", "recommended_slot": "10:30 AM",
                 "predicted_wait_time": "15 min", "predicted_duration_min": 20,
                 "reason": "Lowest load among available Cardiology doctors; no slot conflicts."}
}
```

---

## Beds

### `GET /beds` (admin, doctor)
Query: `ward`, `status`. Response:
```json
{
  "items": [{"id": 1, "bed_id": "ICU-12", "ward": "ICU", "bed_type": "icu",
             "occupancy_status": "occupied", "patient_id": "P00012", "patient_name": "Jane Doe"}],
  "total": 200,
  "summary": [{"ward": "ICU", "total": 30, "occupied": 26, "available": 4, "occupancy_pct": 86.7}]
}
```
`occupancy_status`: `available` | `occupied` | `reserved` | `maintenance`.
`bed_type`: `icu` | `general` | `cardiac` | `pediatric` | `surgical` | `emergency`.

### `POST /beds/allocate` (admin)
Request: `{"patient_ids": null}`. `null` means every admitted patient without a bed.
Runs the OR-Tools bed optimizer and applies the assignments.
```json
{
  "assignments": [{"patient_id": "P05012", "patient_name": "Sam Lee", "severity_score": 9.1,
                   "assigned_bed": "ICU-12", "ward": "ICU"}],
  "unassigned": [{"patient_id": "P05019", "reason": "No ICU bed available"}],
  "utilization_score": 92,
  "solver_status": "OPTIMAL",
  "recommendation_id": 44
}
```

---

## Staff

### `GET /staff` (admin, staff_coordinator)
Query: `department`, `shift` (`morning` | `evening` | `night`). Response:
```json
{
  "items": [{"id": 1, "staff_id": "S001", "name": "Riley Chen", "role": "Nurse",
             "department": "Cardiology", "shift": "morning", "workload_score": 78.0, "on_duty": true}],
  "total": 100,
  "summary": [{"department": "Cardiology", "on_duty": 9, "total": 12, "avg_workload": 72.5,
               "patient_load": 31, "load_ratio": 3.4}]
}
```
`workload_score` is 0–100. `load_ratio` = patients per on-duty staff member.

### `POST /staff/rebalance` (admin, staff_coordinator)
Request: `{"apply": false}`. With `apply: true` the moves are written to the database.
```json
{
  "staff_reallocation": [{"from": "Orthopedics", "to": "Emergency", "staff_count": 3,
                          "staff_ids": ["S014", "S022", "S031"]}],
  "before": [{"department": "Emergency", "load_ratio": 6.1}],
  "after":  [{"department": "Emergency", "load_ratio": 4.2}],
  "solver_status": "OPTIMAL",
  "applied": false,
  "recommendation_id": 45
}
```

---

## Emergency

### `GET /emergency` (admin)
Query: `status` = `active` | `all` (default `active`). Response:
```json
{
  "items": [EmergencyCase],
  "total": 7,
  "surge": {"active_cases": 7, "critical_cases": 2, "baseline_per_hour": 2.1,
            "last_hour": 5, "surge_detected": true}
}
```
`EmergencyCase`:
```json
{"id": 991, "case_id": "E0991", "severity": "critical", "arrival_time": "2026-10-04T02:14:00",
 "department": "Emergency", "response_time": null, "status": "waiting"}
```
`severity`: `critical` | `high` | `moderate` | `low`. `status`: `waiting` | `in_treatment` | `resolved`.
`response_time` is minutes (null while waiting).

### `POST /emergency` (admin)
Request: `{"severity": "critical", "department": "Emergency", "count": 4}` registers incoming
cases and runs the Emergency Response Agent.
```json
{
  "cases": [EmergencyCase],
  "response": {
    "priority_level": "Critical",
    "recommended_actions": ["Reserve 4 ICU beds", "Assign 2 surgeons", "Alert on-call administrator"],
    "reserved_beds": ["ICU-03", "ICU-17"],
    "surge_detected": true
  },
  "recommendation_id": 46
}
```

---

## AI agent

### `POST /agent/query` (all roles)
Request: `{"query": "Which ward is overloaded?"}`

The LangGraph supervisor picks the relevant agents for the question and the user's role. Admins
can reach all five agents; doctors reach scheduling + analytics; coordinators reach staff + analytics.
```json
{
  "answer": "ICU is the most constrained ward at 93% occupancy ...",
  "agents_used": ["resource", "analytics"],
  "outputs": {
    "resource": {"assigned_bed": "ICU-12", "utilization_score": 92, "ward_utilization": [...]},
    "analytics": {"summary": "..."}
  },
  "trace": [{"agent": "supervisor", "summary": "Routed to resource, analytics"},
            {"agent": "resource", "summary": "ICU 93% occupied, 2 beds free"}],
  "llm_calls": 1,
  "model": "nvidia/nemotron-3-super-120b-a12b"
}
```
`outputs` keys are any of `scheduling`, `resource`, `staff`, `emergency`, `analytics`, with the
shapes shown in the agent sections of the README.

Every response also carries the reviewer outcome and run status:
```json
{
  "status": "completed",
  "thread_id": "5b0f6c1e-...",
  "review": {
    "verdict": "approve",
    "revision_count": 1,
    "violations": [{"agent": "staff", "rule": "workload_cap", "detail": "S014 would reach 108 > 100"}],
    "history": [{"attempt": 1, "verdict": "revise", "violations": [...], "feedback": "..."},
                {"attempt": 2, "verdict": "approve", "violations": [], "feedback": ""}]
  },
  "interrupt": null
}
```
`status`: `completed` | `needs_human` | `rejected`. When `needs_human`, `answer` is empty and
`interrupt` holds what the reviewer escalated:
```json
{
  "reason": "infeasible",
  "summary": "12 critical patients need ICU beds but only 3 are free ...",
  "unresolved_violations": [{"agent": "resource", "rule": "icu_capacity", "detail": "..."}],
  "best_outputs": {"resource": {...}, "emergency": {...}},
  "revision_count": 1
}
```
`reason`: `infeasible` | `no_progress` | `cap` (rejected twice).

### `POST /agent/resume` (admin)
Request: `{"thread_id": "5b0f6c1e-...", "action": "approve" | "reject", "note": "Divert to County General"}`
Resumes a run paused for human review. Response: the same shape as `POST /agent/query`, with
`status` `completed` (approved, `answer` filled in) or `rejected`.

---

## Scenarios (admin)

### `GET /scenarios`
`[{"id": "mass_casualty", "name": "Mass Casualty Emergency", "description": "..."}]`
IDs: `normal_day`, `monday_rush`, `icu_shortage`, `mass_casualty`, `staff_shortage`.

### `POST /scenarios/{id}/run`
Applies the scenario to the live hospital state, then runs the full agent pipeline.
```json
{"scenario": {"id": "...", "name": "..."}, "changes": {"emergency_cases_added": 18, "...": 0},
 "agent_run": AgentQueryResponse}
```

### `POST /scenarios/reset`
Restores the baseline seeded state. Response: `{"status": "reset"}`.

---

## Recommendations

### `GET /recommendations` (admin: all; others: their agents' recommendations)
Query: `status` = `pending` | `accepted` | `overridden`, `limit`.
```json
{"id": 44, "agent": "resource", "title": "Allocate 6 beds (utilization 92%)",
 "details": {...}, "status": "pending", "created_at": "2026-10-04T09:31:00",
 "decided_by": null, "override_note": null}
```

### `POST /recommendations/{id}/decision` (admin)
Request: `{"action": "accept" | "override", "note": "Keep ICU-12 for post-op patient"}`.
Response: the updated recommendation.

---

## Health

### `GET /health`
`{"status": "ok", "database": "ok", "llm_model": "nvidia/nemotron-3-super-120b-a12b"}`
