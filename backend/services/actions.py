"""Apply agent decisions to the database (on explicit endpoints or an accepted recommendation)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from core.logging import get_logger
from models import Bed, Staff

log = get_logger("actions")


def apply_bed_assignments(db: Session, assignments: list[dict]) -> int:
    """Occupy beds for the given assignments; skips any bed no longer available."""
    applied = 0
    for a in assignments:
        bed = db.scalar(select(Bed).where(Bed.bed_id == a["assigned_bed"]))
        if bed and bed.occupancy_status == "available":
            bed.occupancy_status, bed.patient_id = "occupied", a["patient_id"]
            applied += 1
    db.commit()
    return applied


def apply_staff_moves(db: Session, moves: list[dict]) -> int:
    applied = 0
    for m in moves:
        s = db.scalar(select(Staff).where(Staff.staff_id == m["staff_id"]))
        if s and s.on_duty and s.department == m["from"]:
            s.department, s.workload_score = m["to"], m["new_workload"]
            applied += 1
    db.commit()
    return applied


def reserve_beds(db: Session, bed_ids: list[str]) -> int:
    applied = 0
    for bed_id in bed_ids:
        bed = db.scalar(select(Bed).where(Bed.bed_id == bed_id))
        if bed and bed.occupancy_status == "available":
            bed.occupancy_status = "reserved"
            applied += 1
    db.commit()
    return applied


def apply_recommendation(db: Session, agent: str, details: dict) -> dict:
    """Execute an accepted recommendation. Scheduling suggestions are advisory only."""
    if agent == "resource":
        return {"beds_assigned": apply_bed_assignments(db, details.get("assignments", []))}
    if agent == "staff":
        return {"staff_moved": apply_staff_moves(db, details.get("moves", []))}
    if agent == "emergency":
        return {"beds_reserved": reserve_beds(db, details.get("reserved_beds", []))}
    return {}
