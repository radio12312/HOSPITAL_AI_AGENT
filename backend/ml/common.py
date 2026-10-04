"""Shared helpers for the XGBoost models: feature encoding and artifact persistence."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

from core.config import ARTIFACT_DIR
from core.constants import DEPARTMENTS


def one_hot_department(series: pd.Series) -> pd.DataFrame:
    """Fixed-column one-hot encoding so training and inference always line up."""
    return pd.DataFrame({f"dept_{d}": (series == d).astype(int) for d in DEPARTMENTS}, index=series.index)


def new_regressor() -> XGBRegressor:
    return XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, subsample=0.9,
                        colsample_bytree=0.9, objective="reg:squarederror", random_state=42)


def time_split(df: pd.DataFrame, date_col: str, test_frac: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = df.sort_values(date_col)
    cut = int(len(df) * (1 - test_frac))
    return df.iloc[:cut], df.iloc[cut:]


def metrics(y_true, y_pred) -> dict[str, float]:
    y_true, y_pred = np.asarray(y_true, float), np.asarray(y_pred, float)
    mae = float(np.mean(np.abs(y_true - y_pred)))
    ss_res = float(np.sum((y_true - y_pred) ** 2))
    ss_tot = float(np.sum((y_true - y_true.mean()) ** 2)) or 1.0
    return {"mae": round(mae, 3), "r2": round(1 - ss_res / ss_tot, 3), "n_test": int(len(y_true))}


def save_model(name: str, model: XGBRegressor, features: list[str], scores: dict) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACT_DIR / f"{name}.json"
    model.save_model(path)
    meta = {"features": features, "metrics": scores, "trained_at": datetime.now().isoformat(timespec="seconds")}
    (ARTIFACT_DIR / f"{name}.meta.json").write_text(json.dumps(meta, indent=2))
    return path


def load_model(name: str) -> tuple[XGBRegressor, dict] | None:
    path = ARTIFACT_DIR / f"{name}.json"
    if not path.exists():
        return None
    model = XGBRegressor()
    model.load_model(path)
    meta = json.loads((ARTIFACT_DIR / f"{name}.meta.json").read_text())
    return model, meta
