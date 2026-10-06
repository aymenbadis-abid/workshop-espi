"""Load the saved Isolation Forest and score one telemetry window.

No fixed temperature or gas limit is used. If the model file is missing, scoring
is skipped and ingestion continues.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import joblib

from app.core.config import settings
from app.modules.ml.features import WINDOW, feature_vector

logger = logging.getLogger(__name__)

_bundle: dict | None = None
_missing_logged = False
_last_alert_at: dict[str, float] = {}
ALERT_COOLDOWN_S = 120.0


def load_model() -> None:
    global _bundle, _missing_logged
    path = Path(settings.anomaly_model_path)
    if not path.is_file():
        _bundle = None
        if not _missing_logged:
            logger.error("Anomaly model not found at %s; scoring is disabled.", path)
            _missing_logged = True
        return
    _bundle = joblib.load(path)
    logger.info("Loaded anomaly model from %s", path)


def score(samples: list[tuple[float, float]]) -> bool:
    """Return True when the window is an anomaly. `samples` is oldest first."""
    if _bundle is None or len(samples) < WINDOW:
        return False
    vector = feature_vector(samples[-WINDOW:]).reshape(1, -1)
    scaled = _bundle["scaler"].transform(vector)
    return int(_bundle["model"].predict(scaled)[0]) == -1


def should_emit(device: str, now: float | None = None) -> bool:
    """Limit repeat anomaly alerts while a drift is still in progress."""
    moment = time.monotonic() if now is None else now
    previous = _last_alert_at.get(device)
    if previous is not None and moment - previous < ALERT_COOLDOWN_S:
        return False
    _last_alert_at[device] = moment
    return True
