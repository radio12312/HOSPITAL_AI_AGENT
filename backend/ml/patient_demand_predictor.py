"""Model 1 - Patient demand: expected admissions per department per day.

Inputs: day_of_week, department, historical_admissions (mean of the previous 7 days).
Output: expected_admissions.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from core.constants import DEPARTMENTS
from ml.common import load_model, metrics, new_regressor, one_hot_department, save_model, time_split

NAME = "patient_demand"


def daily_admissions(patients: pd.DataFrame) -> pd.DataFrame:
    """Admissions per (date, department), zero-filled."""
    df = patients.assign(date=pd.to_datetime(patients["admission_date"]).dt.normalize())
    counts = df.groupby(["date", "department"]).size().rename("admissions")
    idx = pd.MultiIndex.from_product([pd.date_range(df.date.min(), df.date.max()), DEPARTMENTS],
                                     names=["date", "department"])
    return counts.reindex(idx, fill_value=0).reset_index()


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    x = pd.concat([frame[["day_of_week", "historical_admissions"]], one_hot_department(frame["department"])], axis=1)
    return x.astype(float)


def build_training_frame(patients: pd.DataFrame) -> pd.DataFrame:
    df = daily_admissions(patients).sort_values(["department", "date"])
    df["historical_admissions"] = (df.groupby("department")["admissions"]
                                   .transform(lambda s: s.shift(1).rolling(7, min_periods=7).mean()))
    df["day_of_week"] = df["date"].dt.dayofweek
    return df.dropna(subset=["historical_admissions"])


def train(patients: pd.DataFrame) -> dict:
    df = build_training_frame(patients)
    tr, te = time_split(df, "date")
    model = new_regressor().fit(build_features(tr), tr["admissions"])
    scores = metrics(te["admissions"], model.predict(build_features(te)))
    save_model(NAME, model, list(build_features(tr).columns), scores)
    return scores


class PatientDemandPredictor:
    def __init__(self) -> None:
        loaded = load_model(NAME)
        if loaded is None:
            raise FileNotFoundError("patient_demand model not trained - run `python seed_data.py`")
        self.model, self.meta = loaded

    def predict(self, day_of_week: int, department: str, historical_admissions: float) -> float:
        frame = pd.DataFrame([{"day_of_week": day_of_week, "department": department,
                               "historical_admissions": historical_admissions}])
        return max(0.0, float(self.model.predict(build_features(frame))[0]))

    def forecast(self, history: pd.DataFrame, start: date, days: int = 7) -> list[dict]:
        """Recursive multi-day forecast.

        `history`: daily admissions per department (columns date, department, admissions) for at
        least the 7 days before `start`. Predictions feed back in as history for later days.
        """
        hist = {d: list(history[history.department == d].sort_values("date")["admissions"].tail(7))
                for d in DEPARTMENTS}
        out = []
        for i in range(days):
            day = start + timedelta(days=i)
            per_dept = {}
            for d in DEPARTMENTS:
                window = hist[d][-7:] or [0.0]
                pred = self.predict(day.weekday(), d, sum(window) / len(window))
                per_dept[d] = round(pred, 1)
                hist[d].append(pred)
            out.append({"date": day.isoformat(), "expected_admissions": round(sum(per_dept.values()), 1),
                        "by_department": per_dept})
        return out
