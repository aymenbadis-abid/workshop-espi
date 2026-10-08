"""Fit one Isolation Forest on a calm recording of this room.

Temperature and humidity are learned apart, at the board step of 5 s.
Gas and light are not part of this recording. Without 30 minutes of real
calm data and a separate voluntary rise, nothing is saved.

    python api/ml_training/train_room_series.py
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

from app.modules.ml.features import SERIES_FEATURE_NAMES, WINDOW, series_feature_vector  # noqa: E402
from room_recording import load_rows, long_enough, real_rows  # noqa: E402

DATA = Path(__file__).resolve().parent / "data"
MODELS = Path(__file__).resolve().parent / "models"
CALM = DATA / "room_calm.csv"
RISE = DATA / "room_rise.csv"
STEP_S = 5.0


def _windows(rows: list[dict], channel: str, step: int) -> np.ndarray:
    values = [float(row[channel]) for row in rows]
    vectors = [
        series_feature_vector(values[index : index + WINDOW])
        for index in range(0, len(values) - WINDOW + 1, step)
    ]
    if not vectors:
        raise SystemExit(f"Not enough {channel} rows to build a window.")
    return np.vstack(vectors)


def _fit_one(channel: str, calm: list[dict], rise: list[dict]) -> None:
    ordered = sorted(calm, key=lambda row: row["ts"])
    split = max(WINDOW + 1, int(len(ordered) * 0.8))
    train_rows = ordered[:split]
    holdout_rows = ordered[split:]
    if len(holdout_rows) < WINDOW:
        holdout_rows = ordered[-WINDOW * 2 :]
        train_rows = ordered[:-WINDOW]
    train = _windows(train_rows, channel, step=5)
    holdout = _windows(holdout_rows, channel, step=5)
    scaler = StandardScaler()
    model = IsolationForest(n_estimators=200, contamination=0.02, random_state=7, n_jobs=1)
    model.fit(scaler.fit_transform(train))

    def rate(vectors: np.ndarray) -> float:
        labels = model.predict(scaler.transform(vectors))
        return float((labels == -1).mean())

    normal_rate = rate(holdout)
    drift_rate = rate(_windows(rise, channel, step=1))
    print(f"{channel} holdout anomaly rate: {normal_rate:.3f}")
    print(f"{channel} rise anomaly rate: {drift_rate:.3f}")
    if normal_rate > 0.05:
        raise SystemExit(f"{channel} calm holdout is flagged too often. Model not saved.")
    if drift_rate < 0.8:
        raise SystemExit(f"{channel} voluntary rise is not detected. Model not saved.")

    info = {
        "version": f"room-{channel}-1",
        "name": "forêt d'isolation",
        "algorithm": "isolation_forest",
        "trained_on": "room",
        "step_s": STEP_S,
        "window": WINDOW,
        "channels": [channel],
        "feature_names": list(SERIES_FEATURE_NAMES),
        "normal_anomaly_rate": round(normal_rate, 4),
        "drift_anomaly_rate": round(drift_rate, 4),
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "summary": (
            "Forêt d'isolation d'une seule voie, apprise sur la salle calme "
            f"({channel}), au pas de 5 s. Elle ne dit pas que la température "
            "et le gaz montent ensemble."
        ),
    }
    path = MODELS / f"room_{channel}.joblib"
    MODELS.mkdir(parents=True, exist_ok=True)
    joblib.dump({"scaler": scaler, "model": model, "window": WINDOW, "info": info}, path)
    fiche = path.with_suffix(".json")
    fiche.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"saved {path}")


def main() -> None:
    calm = load_rows(CALM)
    if calm is None:
        print(f"No calm room recording at {CALM}. Single-channel models were not saved.")
        return
    rise = load_rows(RISE)
    if rise is None:
        print(f"No voluntary rise at {RISE}. Single-channel models were not saved.")
        return
    saved = False
    for channel in ("temp", "hum"):
        calm_channel = real_rows(calm, (channel,))
        rise_channel = real_rows(rise, (channel,))
        if not long_enough(calm_channel):
            print(f"{channel}: fewer than 30 minutes of real readings. Model not saved.")
            continue
        if len(rise_channel) < WINDOW:
            print(f"{channel}: the rise file has no full real window. Model not saved.")
            continue
        _fit_one(channel, calm_channel, rise_channel)
        saved = True
    if not saved:
        print("No single-channel room model was saved.")


if __name__ == "__main__":
    main()
