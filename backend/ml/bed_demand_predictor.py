"""Model 3 - Bed demand: occupied beds required tomorrow.

Inputs: occupancy_rate (today), admissions (today), emergency_cases (today).
Output: future_bed_requirement (beds occupied the next day).
"""

from __future__ import annotations

import pandas as pd

from ml.common import load_model, metrics, new_regressor, save_model, time_split

NAME = "bed_demand"
FEATURES = ["occupancy_rate", "admissions", "emergency_cases"]


def build_training_frame(patients: pd.DataFrame, emergencies: pd.DataFrame, total_beds: int) -> pd.DataFrame:
    adm = pd.to_datetime(patients["admission_date"])
    dis = pd.to_datetime(patients["discharge_date"])
    days = pd.date_range(adm.min().normalize() + pd.Timedelta(days=14), adm.max().normalize())
    rows = []
    for d in days:
        end = d + pd.Timedelta(days=1)
        census = int(((adm < end) & (dis.isna() | (dis >= end))).sum())
        rows.append({"date": d, "census": min(census, total_beds),
                     "admissions": int(((adm >= d) & (adm < end)).sum())})
    df = pd.DataFrame(rows)
    em = pd.to_datetime(emergencies["arrival_time"]).dt.normalize().value_counts()
    df["emergency_cases"] = df["date"].map(em).fillna(0).astype(int)
    df["occupancy_rate"] = df["census"] / total_beds
    df["future_bed_requirement"] = df["census"].shift(-1)
    return df.dropna(subset=["future_bed_requirement"])


def train(patients: pd.DataFrame, emergencies: pd.DataFrame, total_beds: int) -> dict:
    df = build_training_frame(patients, emergencies, total_beds)
    tr, te = time_split(df, "date")
    model = new_regressor().fit(tr[FEATURES].astype(float), tr["future_bed_requirement"])
    scores = metrics(te["future_bed_requirement"], model.predict(te[FEATURES].astype(float)))
    save_model(NAME, model, FEATURES, scores)
    return scores


class BedDemandPredictor:
    def __init__(self) -> None:
        loaded = load_model(NAME)
        if loaded is None:
            raise FileNotFoundError("bed_demand model not trained - run `python seed_data.py`")
        self.model, self.meta = loaded

    def predict(self, occupancy_rate: float, admissions: int, emergency_cases: int) -> float:
        frame = pd.DataFrame([{"occupancy_rate": occupancy_rate, "admissions": admissions,
                               "emergency_cases": emergency_cases}])
        return max(0.0, float(self.model.predict(frame[FEATURES].astype(float))[0]))
