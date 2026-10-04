"""Hospital simulation engine: applies demo scenarios to the live hospital state.

Every scenario starts from the seeded baseline (so runs are reproducible), then changes the
state: admissions, appointments, emergencies, bed occupancy, staffing shortages. After a
scenario the API runs the full agent workflow so the agents react to the new state.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from core.constants import CRITICAL_SEVERITY, shift_for_hour
from core.logging import get_logger
from database.session import SessionLocal
from models import Appointment, Bed, Doctor, EmergencyCase, Patient, Staff
from seed.generator import DEPT_BASE_WAIT, DEPT_CONSULT_MIN
from seed.loader import load_database, read_csvs
from services.hospital_state import get_now, set_state

log = get_logger("simulator")


@dataclass(frozen=True)
class Scenario:
    id: str
    name: str
    description: str
    inject_fault: bool = False


SCENARIOS: dict[str, Scenario] = {s.id: s for s in [
    Scenario("normal_day", "Normal Operating Day",
             "Baseline mid-week morning: ~80% bed occupancy, routine emergencies, normal staffing."),
    Scenario("monday_rush", "Monday Morning Rush",
             "Monday 09:00: 140 extra morning appointments (Cardiology and General Medicine heavy) and "
             "14 new admissions waiting for beds."),
    Scenario("icu_shortage", "ICU Capacity Shortage",
             "ICU filled to 29/30 by overnight admissions, then 4 more critical patients arrive needing ICU beds."),
    Scenario("mass_casualty", "Mass Casualty Emergency",
             "Multi-vehicle collision: 16 emergency cases (8 critical) in 40 minutes plus 6 critical trauma "
             "admissions. Physically exceeds ICU capacity."),
    Scenario("staff_shortage", "Staff Shortage Event",
             "Sickness wave: a third of on-duty nurses in General Medicine and Cardiology call in sick; remaining "
             "staff workload rises. Demo mechanism: the first staffing plan deliberately breaks the workload cap "
             "so the reviewer's revise path is visible.", inject_fault=True),
]}


class HospitalSimulator:
    def __init__(self, db: Session, seed: int = 7) -> None:
        self.db = db
        self.rng = random.Random(seed)
        self.fake = Faker()
        Faker.seed(seed)

    # ------------------------------------------------------------------ baseline
    @staticmethod
    def reset() -> None:
        """Reload the seeded baseline (CSV snapshot) into the database."""
        load_database(read_csvs())

    # ------------------------------------------------------------------ primitives
    def admit(self, n: int, severity: tuple[float, float], departments: list[str],
              minutes_ago: tuple[int, int] = (5, 90), age: tuple[int, int] = (18, 90)) -> list[Patient]:
        now = get_now(self.db)
        base = self.db.scalar(select(func.count()).select_from(Patient)) or 0
        out = []
        for i in range(n):
            sev = round(self.rng.uniform(*severity), 1)
            p = Patient(patient_id=f"P{base + i + 1:05d}", name=self.fake.name(), age=self.rng.randint(*age),
                        gender=self.rng.choice(["Female", "Male"]), department=self.rng.choice(departments),
                        severity_score=sev, admission_date=now - timedelta(minutes=self.rng.randint(*minutes_ago)),
                        discharge_date=None, treatment_duration=self.rng.randint(8, 20) if sev >= CRITICAL_SEVERITY
                        else self.rng.randint(1, 6))
            self.db.add(p)
            out.append(p)
        self.db.flush()
        return out

    def emergencies(self, severities: list[str], departments: list[str], window_min: int) -> list[EmergencyCase]:
        now = get_now(self.db)
        base = self.db.scalar(select(func.count()).select_from(EmergencyCase)) or 0
        out = []
        for i, sev in enumerate(severities):
            c = EmergencyCase(case_id=f"E{base + i + 1:04d}", severity=sev, department=self.rng.choice(departments),
                              arrival_time=now - timedelta(minutes=self.rng.randint(1, window_min)),
                              response_time=None, status="waiting")
            self.db.add(c)
            out.append(c)
        self.db.flush()
        return out

    def set_clock(self, when: datetime) -> None:
        set_state(self.db, "sim_now", when.isoformat())
        current = shift_for_hour(when.hour)
        weekend = when.weekday() >= 5
        for s in self.db.scalars(select(Staff)):  # shift change: staff on the current shift are on duty
            s.on_duty = s.shift == current and not (weekend and self.rng.random() < 0.3)
        self.db.flush()

    # ------------------------------------------------------------------ scenarios
    def _monday_rush(self) -> dict:
        now = get_now(self.db)
        monday = (now + timedelta(days=(7 - now.weekday()) % 7 or 7)).replace(hour=9, minute=0)
        self.set_clock(monday)
        doctors = list(self.db.scalars(select(Doctor).where(Doctor.availability_status != "off_duty")))
        heavy = [d for d in doctors if d.specialization in ("Cardiology", "General Medicine")]
        base = self.db.scalar(select(func.count()).select_from(Appointment)) or 0
        patients = list(self.db.scalars(select(Patient.patient_id).limit(2000)))
        for i in range(140):
            doc = self.rng.choice(heavy if self.rng.random() < 0.7 else doctors)
            t = monday.replace(hour=self.rng.choice([8, 9, 9, 10, 10, 11, 11]), minute=self.rng.choice([0, 15, 30, 45]))
            self.db.add(Appointment(appointment_id=f"A{base + i + 1:06d}", patient_id=self.rng.choice(patients),
                                    doctor_id=doc.doctor_id, appointment_time=t,
                                    consultation_duration=DEPT_CONSULT_MIN[doc.specialization],
                                    wait_time=DEPT_BASE_WAIT[doc.specialization] + self.rng.randint(10, 35),
                                    status="scheduled" if t >= monday else "completed"))
        admitted = self.admit(14, (2.5, 7.5), ["General Medicine", "Cardiology", "Orthopedics", "Neurology"])
        return {"clock": monday.isoformat(timespec="minutes"), "appointments_added": 140,
                "admissions_waiting_for_beds": len(admitted)}

    def _icu_shortage(self) -> dict:
        free_icu = list(self.db.scalars(select(Bed).where(Bed.bed_type == "icu", Bed.occupancy_status == "available")))
        fill = free_icu[:-1]  # leave exactly one ICU bed free
        overnight = self.admit(len(fill), (8.0, 9.6), ["Cardiology", "Neurology", "Emergency"], (240, 600))
        for bed, p in zip(fill, overnight):
            bed.occupancy_status, bed.patient_id = "occupied", p.patient_id
        new = self.admit(4, (8.2, 9.8), ["Cardiology", "Emergency", "Neurology"], (5, 40))
        return {"icu_beds_filled_overnight": len(fill), "icu_beds_free": 1, "critical_admissions_waiting": len(new)}

    def _mass_casualty(self) -> dict:
        cases = self.emergencies(["critical"] * 8 + ["high"] * 8, ["Emergency", "Surgery", "Orthopedics"], 40)
        trauma = self.admit(6, (8.4, 9.9), ["Emergency", "Surgery"], (5, 35))
        return {"emergency_cases_added": len(cases), "critical_cases_added": 8,
                "critical_trauma_admissions_waiting": len(trauma)}

    def _staff_shortage(self) -> dict:
        nurses = list(self.db.scalars(select(Staff).where(Staff.on_duty.is_(True),
                                                          Staff.department.in_(["General Medicine", "Cardiology"]),
                                                          Staff.role.in_(["Nurse", "Senior Nurse"]))))
        sick = self.rng.sample(nurses, k=max(1, len(nurses) // 3))
        for s in sick:
            s.on_duty = False
        remaining = list(self.db.scalars(select(Staff).where(Staff.on_duty.is_(True))))
        for s in remaining:
            s.workload_score = min(99.0, round(s.workload_score + 10, 1))
        self.db.flush()
        return {"staff_called_in_sick": len(sick), "departments_hit": ["General Medicine", "Cardiology"],
                "workload_increase_for_remaining": 10, "staff_on_duty_now": len(remaining)}

    def apply(self, scenario_id: str) -> dict:
        """Reset to baseline, then apply the scenario. Returns a summary of the changes."""
        if scenario_id not in SCENARIOS:
            raise KeyError(scenario_id)
        self.db.close()  # release locks before the baseline reload drops tables
        self.reset()
        self.db = SessionLocal()
        handler = {"normal_day": lambda: {"reset_to_baseline": True}, "monday_rush": self._monday_rush,
                   "icu_shortage": self._icu_shortage, "mass_casualty": self._mass_casualty,
                   "staff_shortage": self._staff_shortage}[scenario_id]
        changes = handler()
        set_state(self.db, "active_scenario", scenario_id)
        self.db.commit()
        log.info("Scenario %s applied: %s", scenario_id, changes)
        return changes
