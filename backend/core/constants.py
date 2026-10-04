"""Hospital domain constants shared by data generation, optimisation, agents and the API."""

from __future__ import annotations

# Relative inflow per department: Cardiology and General Medicine are the busiest.
DEPARTMENT_WEIGHTS: dict[str, float] = {
    "Cardiology": 0.19, "General Medicine": 0.22, "Orthopedics": 0.10, "Neurology": 0.08,
    "Pediatrics": 0.10, "Oncology": 0.08, "Emergency": 0.13, "Surgery": 0.10,
}
DEPARTMENTS: list[str] = list(DEPARTMENT_WEIGHTS)

# Wards: (ward name, bed type, number of beds, bed-id prefix). 200 beds in total.
WARDS: list[tuple[str, str, int, str]] = [
    ("ICU", "icu", 30, "ICU"),
    ("General", "general", 70, "GEN"),
    ("Cardiology", "cardiac", 30, "CARD"),
    ("Pediatrics", "pediatric", 20, "PED"),
    ("Surgical", "surgical", 30, "SURG"),
    ("Emergency", "emergency", 20, "ER"),
]
WARD_NAMES: list[str] = [w[0] for w in WARDS]

# Preferred ward per department for non-critical inpatients.
DEPARTMENT_WARD: dict[str, str] = {
    "Cardiology": "Cardiology", "General Medicine": "General", "Orthopedics": "Surgical",
    "Neurology": "General", "Pediatrics": "Pediatrics", "Oncology": "General",
    "Emergency": "Emergency", "Surgery": "Surgical",
}

CRITICAL_SEVERITY = 8.0  # severity_score >= 8 -> critical, needs an ICU bed
HIGH_SEVERITY = 6.0

SHIFTS: dict[str, tuple[int, int]] = {"morning": (7, 15), "evening": (15, 23), "night": (23, 7)}

STAFF_ROLES: dict[str, int] = {"Nurse": 55, "Senior Nurse": 10, "Technician": 12, "Paramedic": 8,
                               "Surgeon": 6, "Anesthetist": 4, "Pharmacist": 5}
# Staff the optimiser may move between departments (specialists stay put).
MOVABLE_ROLES: set[str] = {"Nurse", "Senior Nurse", "Technician", "Paramedic"}
WORKLOAD_CAP = 100.0  # workload_score must stay <= this after any reassignment
TARGET_PATIENTS_PER_STAFF = 6.0  # patients per on-duty staff member

EQUIPMENT: dict[str, int] = {"Ventilator": 20, "Infusion Pump": 40, "Cardiac Monitor": 35,
                             "Defibrillator": 12, "Dialysis Machine": 8, "Portable X-Ray": 6,
                             "ECG Machine": 10, "Wheelchair": 30}

EMERGENCY_SEVERITIES: list[str] = ["critical", "high", "moderate", "low"]


def shift_for_hour(hour: int) -> str:
    if 7 <= hour < 15:
        return "morning"
    if 15 <= hour < 23:
        return "evening"
    return "night"
