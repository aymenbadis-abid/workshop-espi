"""Fit an Isolation Forest on normal scenario windows and save it.

The model is trained only on `normal`. A long `drift` window must be scored
as an anomaly, and a fresh normal window must not. Run from the repository
root:

    python api/ml_training/train_isolation_forest.py

    python api/ml_training/train_isolation_forest.py --card

`--card` keeps the saved forest, measures the two rates again, and writes
the model card next to the file. It does not refit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import random

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "simulator"))

from app.modules.ml.features import FEATURE_NAMES, WINDOW, feature_vector  # noqa: E402
from scenario import ScenarioEngine  # noqa: E402

MODEL_PATH = Path(__file__).resolve().parent / "models" / "isolation_forest.joblib"
DT = 3.0
VERSION = "simulator-couple-1"


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


def _info(normal_rate: float, drift_rate: float) -> dict:
    return {
        "version": VERSION,
        "name": "forêt d'isolation",
        "algorithm": "isolation_forest",
        "trained_on": "simulator",
        "scenario": "normal",
        "step_s": DT,
        "window": WINDOW,
        "channels": ["temp", "gas"],
        "feature_names": list(FEATURE_NAMES),
        "normal_anomaly_rate": round(normal_rate, 4),
        "drift_anomaly_rate": round(drift_rate, 4),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": (
            "Forêt d'isolation du scénario normal du simulateur "
            "(pièce fictive vers 24 °C, gaz vers 300, pas de 3 s). "
            "Elle ne juge pas un gaz réel."
        ),
    }


def _save(scaler, model, normal_rate: float, drift_rate: float) -> None:
    info = _info(normal_rate, drift_rate)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "model": model, "window": WINDOW, "info": info}, MODEL_PATH)
    fiche = MODEL_PATH.with_suffix(".json")
    fiche.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {MODEL_PATH}")
    print(f"saved {fiche}")


def fit_and_save() -> None:
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
    _save(scaler, model, normal_rate, drift_rate)


def write_card() -> None:
    """Measure the saved forest and store its card. The trees stay as they are."""
    if not MODEL_PATH.is_file():
        raise SystemExit(f"No model to describe at {MODEL_PATH}")
    bundle = joblib.load(MODEL_PATH)
    scaler = bundle["scaler"]
    model = bundle["model"]

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
        raise SystemExit("Normal windows are flagged too often. Card not written.")
    if drift_rate < 0.8:
        raise SystemExit("A long drift window is not detected. Card not written.")
    _save(scaler, model, normal_rate, drift_rate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--card", action="store_true", help="Write the card for the saved forest.")
    args = parser.parse_args()
    if args.card:
        write_card()
        return
    fit_and_save()


if __name__ == "__main__":
    main()
