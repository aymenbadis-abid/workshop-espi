"""Fit the temperature-gas couple on a calm recording of this room.

This runs only when both channels are real for 30 to 60 minutes, after the
board has finished warming the gas sensor. Until that file exists, the
simulator model is not used on real gas.

    python api/ml_training/train_room_couple.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT / "api"))

from app.modules.ml.features import FEATURE_NAMES, WINDOW, feature_vector  # noqa: E402
from room_recording import load_rows, long_enough, real_rows  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
MODELS = Path(__file__).resolve().parent / "models"
CALM = DATA / "room_couple_calm.csv"
RISE = DATA / "room_couple_rise.csv"
STEP_S = 5.0


def _windows(rows: list[dict], step: int) -> np.ndarray:
    samples = [(float(row["temp"]), float(row["gas"])) for row in rows]
    vectors = [
        feature_vector(samples[index : index + WINDOW])
        for index in range(0, len(samples) - WINDOW + 1, step)
    ]
    if not vectors:
        raise SystemExit("Not enough real couple rows to build a window.")
    return np.vstack(vectors)


def main() -> None:
    calm_raw = load_rows(CALM)
    if calm_raw is None:
        print(f"No real-gas calm recording at {CALM}. Room couple model was not saved.")
        return
    rise_raw = load_rows(RISE)
    if rise_raw is None:
        print(f"No real-gas rise at {RISE}. Room couple model was not saved.")
        return
    calm = real_rows(calm_raw, ("temp", "gas"))
    rise = real_rows(rise_raw, ("temp", "gas"))
    if not long_enough(calm):
        print("Fewer than 30 minutes of real temperature and real gas. Model not saved.")
        return
    if len(rise) < WINDOW:
        print("The rise file has no full window of real temperature and real gas. Model not saved.")
        return

    ordered = sorted(calm, key=lambda row: row["ts"])
    split = max(WINDOW + 1, int(len(ordered) * 0.8))
    train_rows = ordered[:split]
    holdout_rows = ordered[split:]
    if len(holdout_rows) < WINDOW:
        holdout_rows = ordered[-WINDOW * 2 :]
        train_rows = ordered[:-WINDOW]
    scaler = StandardScaler()
    model = IsolationForest(n_estimators=200, contamination=0.02, random_state=7, n_jobs=1)
    model.fit(scaler.fit_transform(_windows(train_rows, step=5)))

    def rate(vectors: np.ndarray) -> float:
        labels = model.predict(scaler.transform(vectors))
        return float((labels == -1).mean())

    normal_rate = rate(_windows(holdout_rows, step=5))
    drift_rate = rate(_windows(rise, step=1))
    print(f"couple holdout anomaly rate: {normal_rate:.3f}")
    print(f"couple rise anomaly rate: {drift_rate:.3f}")
    if normal_rate > 0.05:
        raise SystemExit("Calm real couple is flagged too often. Model not saved.")
    if drift_rate < 0.8:
        raise SystemExit("Real couple rise is not detected. Model not saved.")

    info = {
        "version": "room-couple-1",
        "name": "forêt d'isolation",
        "algorithm": "isolation_forest",
        "trained_on": "room",
        "step_s": STEP_S,
        "window": WINDOW,
        "channels": ["temp", "gas"],
        "feature_names": list(FEATURE_NAMES),
        "normal_anomaly_rate": round(normal_rate, 4),
        "drift_anomaly_rate": round(drift_rate, 4),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": (
            "Forêt d'isolation du couple température–gaz, apprise sur la salle "
            "quand les deux voies sont réelles. Le pic franc reste la phrase de la carte."
        ),
    }
    path = MODELS / "room_couple.joblib"
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "model": model, "window": WINDOW, "info": info}, path)
    fiche = path.with_suffix(".json")
    fiche.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {path}")


if __name__ == "__main__":
    main()
