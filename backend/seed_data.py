"""Generate synthetic data, load the database, train the ML models and create demo users.

    python seed_data.py            # full reset: new CSVs + database + models
    python seed_data.py --if-empty # only seed when the database has no data (used by Docker)
"""

from __future__ import annotations

import argparse
import sys
import time

from sqlalchemy import inspect, select

from core.config import ARTIFACT_DIR, DATA_DIR, settings
from core.logging import get_logger, setup_logging
from database.session import SessionLocal, engine
from ml.train import train_all
from models import User
from seed.generator import HospitalDataGenerator
from seed.loader import CSV_FILES, load_database, write_csvs

MODELS = ("patient_demand", "waiting_time", "bed_demand")

log = get_logger("seed")


def already_seeded() -> bool:
    """Database populated AND the CSV snapshot and trained models exist."""
    if not inspect(engine).has_table("users"):
        return False
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            return False
    files = [DATA_DIR / f for f in CSV_FILES.values()] + [ARTIFACT_DIR / f"{m}.json" for m in MODELS]
    return all(f.exists() for f in files)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--if-empty", action="store_true", help="skip if the database already has data")
    args = parser.parse_args()
    setup_logging()

    if args.if_empty and already_seeded():
        log.info("Database already seeded - skipping (run without --if-empty to reset)")
        return 0

    t0 = time.perf_counter()
    log.info("Generating synthetic hospital data ...")
    ds = HospitalDataGenerator().generate()
    write_csvs(ds)
    log.info("Loading database (%s) ...", settings.database_url.split("@")[-1])
    load_database(ds)
    log.info("Training XGBoost models ...")
    train_all(ds)
    log.info("Done in %.1fs. Hospital clock set to %s. Demo users: admin/admin123, doctor/doctor123, "
             "coordinator/coord123", time.perf_counter() - t0, ds.anchor.strftime("%a %d %b %Y %H:%M"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
