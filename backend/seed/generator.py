"""Seeded synthetic hospital dataset generator (Faker + pandas + NumPy).

Realistic patterns encoded here:
  1. Mondays have the highest admissions (weekday weights).
  2. Appointments peak 8 AM - 12 PM (hourly weights).
  3. Emergency cases rise at night (20:00 - 04:00).
  4. ICU occupancy is held between 70 % and 95 %.
  5. Cardiology and General Medicine have the highest inflow.
  6. Weekends have lower staffing (fewer staff on duty).
  7. Seasonal spikes: flu season (Dec - Feb), a viral outbreak window, holiday surges.
  8. Critical patients get high severity, long stays and a high ICU probability.

All data is synthetic. No real patient information is used.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from faker import Faker

from core.constants import (
    CRITICAL_SEVERITY, DEPARTMENT_WARD, DEPARTMENT_WEIGHTS, DEPARTMENTS, EMERGENCY_SEVERITIES,
    EQUIPMENT, STAFF_ROLES, WARDS, shift_for_hour,
)

SEED = 42
WEEKDAY_WEIGHT = np.array([1.30, 1.10, 1.00, 1.00, 0.95, 0.75, 0.70])  # Mon..Sun
APPT_HOUR_WEIGHT = {8: 1.6, 9: 1.8, 10: 1.8, 11: 1.6, 12: 1.0, 13: 0.8, 14: 0.9, 15: 0.9, 16: 0.7, 17: 0.5}
DEPT_SEVERITY = {"Cardiology": 5.6, "General Medicine": 4.4, "Orthopedics": 4.2, "Neurology": 5.2,
                 "Pediatrics": 3.8, "Oncology": 5.4, "Emergency": 6.0, "Surgery": 5.0}
DEPT_CONSULT_MIN = {"Cardiology": 22, "General Medicine": 15, "Orthopedics": 18, "Neurology": 25,
                    "Pediatrics": 16, "Oncology": 28, "Emergency": 12, "Surgery": 24}
DEPT_BASE_WAIT = {"Cardiology": 14, "General Medicine": 12, "Orthopedics": 9, "Neurology": 11,
                  "Pediatrics": 8, "Oncology": 10, "Emergency": 6, "Surgery": 10}


@dataclass
class Dataset:
    anchor: datetime
    patients: pd.DataFrame
    doctors: pd.DataFrame
    appointments: pd.DataFrame
    staff: pd.DataFrame
    beds: pd.DataFrame
    emergency_cases: pd.DataFrame
    equipment: pd.DataFrame


def default_anchor(today: date | None = None) -> datetime:
    """The hospital clock: the most recent Wednesday (a normal weekday) at 10:30."""
    today = today or date.today()
    wed = today - timedelta(days=(today.weekday() - 2) % 7)
    return datetime(wed.year, wed.month, wed.day, 10, 30)


def seasonal_factor(d: date, department: str | None = None, anchor: date | None = None) -> float:
    """Multiplicative demand factor for flu season, a viral outbreak and holidays."""
    f = 1.0
    if d.month in (12, 1, 2) and department in (None, "General Medicine", "Pediatrics", "Emergency"):
        f *= 1.30  # flu season
    if anchor is not None and 70 <= (anchor - d).days <= 90:
        f *= 1.40  # three-week viral outbreak about 2.5 months before the anchor
    if (d.month == 12 and d.day >= 24) or (d.month == 1 and d.day <= 2):
        f *= 1.25 if department in (None, "Emergency") else 1.0  # holiday surge
    return f


class HospitalDataGenerator:
    def __init__(self, anchor: datetime | None = None, seed: int = SEED) -> None:
        self.anchor = anchor or default_anchor()
        self.rng = np.random.default_rng(seed)
        self.fake = Faker()
        Faker.seed(seed)

    # ------------------------------------------------------------------ helpers
    def _days(self, n_back: int, n_fwd: int = 0) -> list[date]:
        start = self.anchor.date() - timedelta(days=n_back)
        return [start + timedelta(days=i) for i in range(n_back + n_fwd + 1)]

    def _pick(self, options: list, weights, size: int | None = None):
        w = np.asarray(weights, dtype=float)
        return self.rng.choice(options, size=size, p=w / w.sum())

    # ------------------------------------------------------------------ entities
    def doctors(self, n: int = 50) -> pd.DataFrame:
        depts = self._pick(DEPARTMENTS, list(DEPARTMENT_WEIGHTS.values()), n)
        # make sure every department has at least 3 doctors
        for i, d in enumerate(DEPARTMENTS * 3):
            depts[i] = d
        status = self._pick(["available", "busy", "off_duty"], [0.80, 0.12, 0.08], n)
        return pd.DataFrame({
            "doctor_id": [f"D{i + 1:03d}" for i in range(n)],
            "name": [f"Dr. {self.fake.first_name()} {self.fake.last_name()}" for _ in range(n)],
            "specialization": depts,
            "experience_years": self.rng.integers(2, 31, n),
            "daily_capacity": self.rng.integers(12, 25, n),
            "availability_status": status,
        })

    def patients(self, n: int = 5000, days_back: int = 120) -> pd.DataFrame:
        days = self._days(days_back)[:-1] + [self.anchor.date()]
        anchor_d = self.anchor.date()
        dept_w = np.array(list(DEPARTMENT_WEIGHTS.values()))
        rows = []
        # intensity per (day, department) -> sample admissions proportionally
        weights = np.array([[WEEKDAY_WEIGHT[d.weekday()] * seasonal_factor(d, dep, anchor_d) * dw
                             for dep, dw in zip(DEPARTMENTS, dept_w)] for d in days])
        flat = weights.ravel() / weights.sum()
        picks = self.rng.choice(len(flat), size=n, p=flat)
        for k, idx in enumerate(sorted(picks)):
            d, dep = days[idx // len(DEPARTMENTS)], DEPARTMENTS[idx % len(DEPARTMENTS)]
            hour = int(self.rng.integers(0, 24)) if dep == "Emergency" else int(self.rng.integers(7, 20))
            adm = datetime(d.year, d.month, d.day, hour, int(self.rng.integers(0, 60)))
            if adm > self.anchor:
                adm = self.anchor - timedelta(minutes=int(self.rng.integers(5, 300)))
            sev = float(np.clip(self.rng.normal(DEPT_SEVERITY[dep], 1.8), 1.0, 10.0))
            if self.rng.random() < 0.06:  # a tail of genuinely critical cases
                sev = float(self.rng.uniform(8.0, 10.0))
            sev = round(sev, 1)
            critical = sev >= CRITICAL_SEVERITY
            stay = self.rng.lognormal(math.log(11 if critical else 3), 0.45)
            stay = int(np.clip(round(stay), 1, 35 if critical else 14))
            age = int(self.rng.integers(1, 16)) if dep == "Pediatrics" else int(np.clip(self.rng.normal(55, 18), 18, 95))
            discharge = adm + timedelta(days=stay, hours=int(self.rng.integers(0, 12)))
            rows.append({
                "patient_id": f"P{k + 1:05d}",
                "patient_name": self.fake.name(),
                "age": age,
                "gender": self._pick(["Female", "Male"], [0.51, 0.49]),
                "department": dep,
                "severity_score": sev,
                "admission_date": adm,
                "discharge_date": discharge if discharge <= self.anchor else pd.NaT,
                "treatment_duration": stay,
            })
        df = pd.DataFrame(rows)
        df["admission_date"] = pd.to_datetime(df["admission_date"])
        df["discharge_date"] = pd.to_datetime(df["discharge_date"])
        return df

    def beds_and_census(self, patients: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Create 200 beds and assign current inpatients so occupancy is realistic.

        Returns (beds, patients) where over-capacity inpatients are marked discharged and a
        handful of the most recent admissions are left waiting for a bed (for the optimiser).
        """
        beds = []
        for ward, btype, n, prefix in WARDS:
            for i in range(1, n + 1):
                beds.append({"bed_id": f"{prefix}-{i:02d}", "ward": ward, "bed_type": btype,
                             "occupancy_status": "available", "patient_id": None})
        beds = pd.DataFrame(beds)
        maint = self.rng.choice(beds.index[beds.ward != "ICU"], size=3, replace=False)
        beds.loc[maint, "occupancy_status"] = "maintenance"

        inpatients = patients[patients.discharge_date.isna()].sort_values("admission_date")
        waiting = inpatients.tail(6)  # newest admissions: still waiting for a bed
        to_place = inpatients.drop(waiting.index)

        capacity = {w[0]: w[2] for w in WARDS}
        target = {w: int(c * self.rng.uniform(0.72, 0.86)) for w, c in capacity.items()}
        target["ICU"] = int(capacity["ICU"] * self.rng.uniform(0.80, 0.90))  # 70-95 % rule

        placed: dict[str, list[str]] = {w: [] for w in capacity}
        # ICU first: the most severe inpatients
        for pid in to_place.sort_values("severity_score", ascending=False).patient_id:
            if len(placed["ICU"]) >= target["ICU"]:
                break
            placed["ICU"].append(pid)
        rest = to_place[~to_place.patient_id.isin(placed["ICU"])]
        overflow = []
        for _, p in rest.iterrows():
            ward = "Pediatrics" if p.age < 16 else DEPARTMENT_WARD[p.department]
            if len(placed[ward]) < target[ward]:
                placed[ward].append(p.patient_id)
            elif len(placed["General"]) < target["General"]:
                placed["General"].append(p.patient_id)
            else:
                overflow.append(p.patient_id)

        for ward, pids in placed.items():
            free = beds.index[(beds.ward == ward) & (beds.occupancy_status == "available")][: len(pids)]
            beds.loc[free, "occupancy_status"] = "occupied"
            beds.loc[free, "patient_id"] = pids[: len(free)]

        # Inpatients that don't fit were discharged earlier than planned.
        patients = patients.copy()
        mask = patients.patient_id.isin(overflow)
        patients.loc[mask, "discharge_date"] = self.anchor - pd.to_timedelta(
            self.rng.integers(1, 48, mask.sum()), unit="h")
        return beds, patients

    def appointments(self, patients: pd.DataFrame, doctors: pd.DataFrame, n: int = 20000,
                     days_back: int = 150, days_fwd: int = 7) -> pd.DataFrame:
        days = self._days(days_back, days_fwd)
        anchor_d = self.anchor.date()
        day_w = np.array([WEEKDAY_WEIGHT[d.weekday()] * seasonal_factor(d, None, anchor_d)
                          * (0.25 if d.weekday() >= 5 else 1.0) for d in days])
        hours, hour_w = list(APPT_HOUR_WEIGHT), list(APPT_HOUR_WEIGHT.values())
        doc_by_dept = {d: doctors[doctors.specialization == d] for d in DEPARTMENTS}
        pat_by_dept = {d: patients[patients.department == d].patient_id.to_numpy() for d in DEPARTMENTS}
        dept_w = list(DEPARTMENT_WEIGHTS.values())

        day_idx = self._pick(list(range(len(days))), day_w, n)
        dept = self._pick(DEPARTMENTS, dept_w, n)
        hour = self._pick(hours, hour_w, n)
        rows = []
        for i in range(n):
            d, dep = days[day_idx[i]], dept[i]
            doc = doc_by_dept[dep].iloc[int(self.rng.integers(0, len(doc_by_dept[dep])))]
            t = datetime(d.year, d.month, d.day, int(hour[i]), int(self.rng.choice([0, 15, 30, 45])))
            rows.append({"doctor_id": doc.doctor_id, "department": dep, "appointment_time": t,
                         "patient_id": self.rng.choice(pat_by_dept[dep]),
                         "daily_capacity": int(doc.daily_capacity)})
        df = pd.DataFrame(rows).sort_values("appointment_time").reset_index(drop=True)
        df["date"] = df.appointment_time.dt.date
        df["hour"] = df.appointment_time.dt.hour
        df["doctor_load"] = df.groupby(["doctor_id", "date"]).doctor_id.transform("size")
        df["appointments_count"] = df.groupby(["department", "date", "hour"]).doctor_id.transform("size")
        # Wait time grows with doctor overload and same-hour congestion, plus noise.
        overload = (df.doctor_load / df.daily_capacity).clip(lower=0)
        df["wait_time"] = (df.department.map(DEPT_BASE_WAIT) + 22 * np.maximum(overload - 0.6, 0)
                           + 1.8 * df.appointments_count + self.rng.normal(0, 4, len(df))).clip(2, 120).round()
        sev = df.patient_id.map(patients.set_index("patient_id").severity_score)
        df["consultation_duration"] = (df.department.map(DEPT_CONSULT_MIN) + 1.5 * (sev - 5)
                                       + self.rng.normal(0, 3, len(df))).clip(8, 60).round()
        past = df.appointment_time < self.anchor
        df["status"] = "scheduled"
        df.loc[past, "status"] = self._pick(["completed", "no_show", "cancelled"], [0.85, 0.07, 0.08], past.sum())
        df["appointment_id"] = [f"A{i + 1:06d}" for i in range(len(df))]
        return df[["appointment_id", "patient_id", "doctor_id", "appointment_time", "consultation_duration",
                   "wait_time", "status", "department", "doctor_load", "appointments_count"]].astype(
            {"consultation_duration": int, "wait_time": int})

    def staff(self, n: int = 100) -> pd.DataFrame:
        roles = [r for r, c in STAFF_ROLES.items() for _ in range(c)][:n]
        self.rng.shuffle(roles)
        dept = self._pick(DEPARTMENTS, list(DEPARTMENT_WEIGHTS.values()), n)
        for i, d in enumerate(DEPARTMENTS * 2):  # every department gets some staff
            dept[i] = d
        shift = self._pick(["morning", "evening", "night"], [0.40, 0.33, 0.27], n)
        current = shift_for_hour(self.anchor.hour)
        weekend = self.anchor.weekday() >= 5
        on_duty = (shift == current) & (self.rng.random(n) > (0.30 if weekend else 0.05))
        workload = np.clip(self.rng.normal(64, 14, n) + np.where(on_duty, 6, -10), 15, 97).round(1)
        return pd.DataFrame({
            "staff_id": [f"S{i + 1:03d}" for i in range(n)],
            "name": [self.fake.name() for _ in range(n)],
            "role": roles, "department": dept, "shift": shift,
            "workload_score": workload, "on_duty": on_duty,
        })

    def emergency_cases(self, n: int = 1000, days_back: int = 365) -> pd.DataFrame:
        days = self._days(days_back)
        anchor_d = self.anchor.date()
        hour_w = np.array([1.8 if (h >= 20 or h < 4) else (1.2 if h < 8 else 1.0) for h in range(24)])
        day_w = np.array([seasonal_factor(d, "Emergency", anchor_d) for d in days])
        slots = (day_w[:, None] * hour_w[None, :]).ravel()
        picks = np.sort(self.rng.choice(len(slots), size=n, p=slots / slots.sum()))
        sev = self._pick(EMERGENCY_SEVERITIES, [0.10, 0.25, 0.40, 0.25], n)
        resp_range = {"critical": (2, 10), "high": (5, 20), "moderate": (15, 45), "low": (30, 90)}
        rows = []
        for i, s in enumerate(picks):
            d, h = days[s // 24], s % 24
            t = datetime(d.year, d.month, d.day, int(h), int(self.rng.integers(0, 60)))
            if t > self.anchor:
                t = self.anchor - timedelta(minutes=int(self.rng.integers(10, 600)))
            lo, hi = resp_range[sev[i]]
            rows.append({"case_id": f"E{i + 1:04d}", "severity": sev[i], "arrival_time": t,
                         "department": self._pick(["Emergency", "Cardiology", "Neurology", "Surgery", "Orthopedics"],
                                                  [0.60, 0.12, 0.08, 0.10, 0.10]),
                         "response_time": int(self.rng.integers(lo, hi + 1)), "status": "resolved"})
        df = pd.DataFrame(rows).sort_values("arrival_time").reset_index(drop=True)
        df["case_id"] = [f"E{i + 1:04d}" for i in range(len(df))]
        # The most recent few cases are still active.
        recent = df.index[-7:]
        df.loc[recent[:4], "status"] = "in_treatment"
        df.loc[recent[4:], ["status", "response_time"]] = ["waiting", None]
        df.loc[recent[-1], "severity"] = "critical"
        return df

    def equipment(self, occupancy: float) -> pd.DataFrame:
        rows, k = [], 0
        for etype, count in EQUIPMENT.items():
            for _ in range(count):
                k += 1
                r = self.rng.random()
                status = "maintenance" if r < 0.05 else ("in_use" if r < 0.05 + occupancy * 0.85 else "available")
                rows.append({"equipment_id": f"EQ{k:04d}", "type": etype, "availability_status": status})
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------ all
    def generate(self) -> Dataset:
        doctors = self.doctors()
        patients = self.patients()
        beds, patients = self.beds_and_census(patients)
        occupancy = (beds.occupancy_status == "occupied").mean()
        return Dataset(
            anchor=self.anchor, patients=patients, doctors=doctors,
            appointments=self.appointments(patients, doctors), staff=self.staff(), beds=beds,
            emergency_cases=self.emergency_cases(), equipment=self.equipment(float(occupancy)),
        )
