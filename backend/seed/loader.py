"""Write generated datasets to CSV and load them into the database."""

from __future__ import annotations

from datetime import datetime

import pandas as pd
from sqlalchemy import insert
from sqlalchemy.orm import Session

from core.config import DATA_DIR
from core.logging import get_logger
from core.security import hash_password
from database.session import Base, engine
from models import Appointment, Bed, Doctor, EmergencyCase, Equipment, Patient, Staff, SystemState, User
from seed.generator import Dataset

log = get_logger("seed")

CSV_FILES = {"patients": "patients.csv", "doctors": "doctors.csv", "appointments": "appointments.csv",
             "staff": "staff.csv", "beds": "beds.csv", "emergency_cases": "emergency_cases.csv",
             "equipment": "equipment.csv"}

DEMO_USERS = [
    # (username, password, role, email)
    ("admin", "admin123", "admin", "admin@hospital.local"),
    ("doctor", "doctor123", "doctor", "doctor@hospital.local"),
    ("coordinator", "coord123", "staff_coordinator", "coordinator@hospital.local"),
]


def write_csvs(ds: Dataset) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for attr, fname in CSV_FILES.items():
        getattr(ds, attr).to_csv(DATA_DIR / fname, index=False)
    (DATA_DIR / "anchor.txt").write_text(ds.anchor.isoformat())
    log.info("Wrote %d CSV files to %s", len(CSV_FILES), DATA_DIR)


def read_csvs() -> Dataset:
    def rd(name: str, dates: list[str]) -> pd.DataFrame:
        return pd.read_csv(DATA_DIR / CSV_FILES[name], parse_dates=dates)

    return Dataset(
        anchor=datetime.fromisoformat((DATA_DIR / "anchor.txt").read_text().strip()),
        patients=rd("patients", ["admission_date", "discharge_date"]),
        doctors=rd("doctors", []),
        appointments=rd("appointments", ["appointment_time"]),
        staff=rd("staff", []),
        beds=rd("beds", []),
        emergency_cases=rd("emergency_cases", ["arrival_time"]),
        equipment=rd("equipment", []),
    )


def _records(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    out = df[columns].astype(object).where(df[columns].notna(), None)
    return out.to_dict("records")


def load_database(ds: Dataset) -> None:
    """Drop and recreate all tables, then bulk-load the dataset and demo users."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        patients = ds.patients.rename(columns={"patient_name": "name"})
        db.execute(insert(Patient), _records(patients, ["patient_id", "name", "age", "gender", "department",
                                                        "severity_score", "admission_date", "discharge_date",
                                                        "treatment_duration"]))
        db.execute(insert(Doctor), _records(ds.doctors, ["doctor_id", "name", "specialization", "experience_years",
                                                         "daily_capacity", "availability_status"]))
        db.execute(insert(Appointment), _records(ds.appointments, ["appointment_id", "patient_id", "doctor_id",
                                                                   "appointment_time", "consultation_duration",
                                                                   "wait_time", "status"]))
        db.execute(insert(Staff), _records(ds.staff, ["staff_id", "name", "role", "department", "shift",
                                                      "workload_score", "on_duty"]))
        db.execute(insert(Bed), _records(ds.beds, ["bed_id", "ward", "bed_type", "occupancy_status", "patient_id"]))
        db.execute(insert(EmergencyCase), _records(ds.emergency_cases, ["case_id", "severity", "arrival_time",
                                                                        "department", "response_time", "status"]))
        db.execute(insert(Equipment), _records(ds.equipment, ["equipment_id", "type", "availability_status"]))

        cardiology_doc = ds.doctors[ds.doctors.specialization == "Cardiology"].doctor_id.iloc[0]
        for username, password, role, email in DEMO_USERS:
            db.add(User(username=username, email=email, hashed_password=hash_password(password), role=role,
                        doctor_id=cardiology_doc if role == "doctor" else None))
        db.add(SystemState(key="sim_now", value=ds.anchor.isoformat()))
        db.add(SystemState(key="baseline_anchor", value=ds.anchor.isoformat()))
        db.commit()
    log.info("Loaded %d patients, %d doctors, %d appointments, %d staff, %d beds, %d emergency cases, "
             "%d equipment and %d users", len(ds.patients), len(ds.doctors), len(ds.appointments), len(ds.staff),
             len(ds.beds), len(ds.emergency_cases), len(ds.equipment), len(DEMO_USERS))
