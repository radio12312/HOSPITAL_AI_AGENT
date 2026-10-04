"""Model 2 - Waiting time: expected wait (minutes) for an appointment.

Inputs: doctor_load (doctor's appointments that day), appointments_count (same department,
same hour), department. Output: expected_wait_time.
"""

from __future__ import annotations

import pandas as pd

from ml.common import load_model, metrics, new_regressor, one_hot_department, save_model, time_split

NAME = "waiting_time"


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    x = pd.concat([frame[["doctor_load", "appointments_count"]], one_hot_department(frame["department"])], axis=1)
    return x.astype(float)


def build_training_frame(appointments: pd.DataFrame) -> pd.DataFrame:
    df = appointments[appointments["status"].isin(["completed", "no_show"])].copy()
    if "doctor_load" not in df or "appointments_count" not in df:
        t = pd.to_datetime(df["appointment_time"])
        df["date"], df["hour"] = t.dt.date, t.dt.hour
        df["doctor_load"] = df.groupby(["doctor_id", "date"]).doctor_id.transform("size")
        df["appointments_count"] = df.groupby(["department", "date", "hour"]).doctor_id.transform("size")
    return df


def train(appointments: pd.DataFrame) -> dict:
    df = build_training_frame(appointments)
    tr, te = time_split(df, "appointment_time")
    model = new_regressor().fit(build_features(tr), tr["wait_time"])
    scores = metrics(te["wait_time"], model.predict(build_features(te)))
    save_model(NAME, model, list(build_features(tr).columns), scores)
    return scores


class WaitingTimePredictor:
    def __init__(self) -> None:
        loaded = load_model(NAME)
        if loaded is None:
            raise FileNotFoundError("waiting_time model not trained - run `python seed_data.py`")
        self.model, self.meta = loaded

    def predict(self, doctor_load: int, appointments_count: int, department: str) -> float:
        frame = pd.DataFrame([{"doctor_load": doctor_load, "appointments_count": appointments_count,
                               "department": department}])
        return max(1.0, float(self.model.predict(build_features(frame))[0]))

    def predict_many(self, rows: list[dict]) -> list[float]:
        if not rows:
            return []
        return [max(1.0, float(v)) for v in self.model.predict(build_features(pd.DataFrame(rows)))]
