"""Train all three XGBoost models from the generated CSVs.

    python -m ml.train        (run from backend/)
"""

from __future__ import annotations

from core.logging import get_logger, setup_logging
from ml import bed_demand_predictor, patient_demand_predictor, waiting_time_predictor
from seed.generator import Dataset

log = get_logger("ml.train")


def train_all(ds: Dataset) -> dict[str, dict]:
    results = {
        "patient_demand": patient_demand_predictor.train(ds.patients),
        "waiting_time": waiting_time_predictor.train(ds.appointments),
        "bed_demand": bed_demand_predictor.train(ds.patients, ds.emergency_cases, len(ds.beds)),
    }
    for name, m in results.items():
        log.info("Trained %-15s MAE=%-7s R2=%-6s (n_test=%s)", name, m["mae"], m["r2"], m["n_test"])
    return results


def main() -> None:
    from seed.loader import read_csvs

    setup_logging()
    train_all(read_csvs())


if __name__ == "__main__":
    main()
