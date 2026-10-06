"""Fit an Isolation Forest on normal scenario windows and save it.

The model is trained only on `normal`. A long `drift` window must be scored
as an anomaly, and a fresh normal window must not. Run from the repository
root:

    python api/ml_training/train_isolation_forest.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import random

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "simulator"))

from app.modules.ml.features import WINDOW, feature_vector  # noqa: E402
from scenario import ScenarioEngine  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parent / "models" / "isolation_forest.joblib"
DT = 3.0


def collect(scenario: str, count: int, seed: int, start_elapsed: float = 0.0) -> list[tuple[float, float]]:
    engine = ScenarioEngine(random.Random(seed))
    engine.set_scenario(scenario)
    engine.elapsed = start_elapsed
    rows: list[tuple[float, float]] = []
    for _ in range(count):
        sample = engine.step(DT)
        rows.append((sample.temp, sample.gas))
    return rows


def windows_from(rows: list[tuple[float, float]], step: int = 5) -> np.ndarray:
    vectors = [
        feature_vector(rows[index : index + WINDOW])
        for index in range(0, len(rows) - WINDOW + 1, step)
    ]
    return np.vstack(vectors)


def main() -> None:
    normal = windows_from(collect("normal", 2500, seed=7), step=5)
    scaler = StandardScaler()
    scaled = scaler.fit_transform(normal)
    model = IsolationForest(
        n_estimators=200,
        contamination=0.02,
        random_state=7,
        n_jobs=1,
    )
    model.fit(scaled)

    def anomaly_rate(vectors: np.ndarray) -> float:
        labels = model.predict(scaler.transform(vectors))
        return float((labels == -1).mean())

    holdout = windows_from(collect("normal", 800, seed=99), step=10)
    late_drift = windows_from(
        collect("drift", WINDOW + 5, seed=3, start_elapsed=900.0),
        step=1,
    )
    normal_rate = anomaly_rate(holdout)
    drift_rate = anomaly_rate(late_drift)
    print(f"normal anomaly rate: {normal_rate:.3f}")
    print(f"late drift anomaly rate: {drift_rate:.3f}")
    if normal_rate > 0.05:
        raise SystemExit("Normal windows are flagged too often.")
    if drift_rate < 0.8:
        raise SystemExit("A long drift window is not detected.")

    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "model": model, "window": WINDOW}, MODEL_PATH)
    print(f"saved {MODEL_PATH}")


if __name__ == "__main__":
    main()
