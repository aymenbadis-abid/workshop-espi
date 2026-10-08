"""Load saved Isolation Forests and score one telemetry window.

Fixed room limits (27 °C, 33 °C, gas delta) stay on the board. This module
only names a shape. If a model file is missing, that score is skipped and
ingestion continues. A local language model is not loaded.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Sequence

import joblib

from app.modules.ml.decide import Assessment, decide, usable_room_couple, usable_series, usable_simulator
from app.modules.ml.gate import should_emit, silence_line

logger = logging.getLogger(__name__)

_simulator: dict | None = None
_room_temp: dict | None = None
_room_hum: dict | None = None
_room_couple: dict | None = None
_missing_logged = False
_status: dict[str, dict] = {}
_last_pause: dict[str, str | None] = {}
_last_skip: dict[str, str | None] = {}
_last_silence: dict[str, str | None] = {}


def _load_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    loaded = joblib.load(path)
    if not isinstance(loaded, dict) or "model" not in loaded or "scaler" not in loaded:
        logger.error("Refusing %s: the file is not a scoring bundle.", path)
        return None
    if "info" not in loaded:
        fiche = path.with_suffix(".json")
        if fiche.is_file():
            loaded["info"] = json.loads(fiche.read_text(encoding="utf-8"))
    return loaded


def _load_room(path: Path, kind: str) -> dict | None:
    if not path.is_file():
        logger.info("Room model %s is not on disk (%s); that score stays off.", kind, path)
        return None
    bundle = _load_file(path)
    if bundle is None:
        return None
    usable = usable_room_couple(bundle) if kind == "couple" else usable_series(bundle, kind)
    if usable is None:
        logger.error("Refusing %s at %s: it is not a room model for this channel.", kind, path)
        return None
    logger.info("Loaded room model %s from %s", kind, path)
    return usable


def load_model() -> None:
    global _simulator, _room_temp, _room_hum, _room_couple, _missing_logged
    from app.core.config import settings

    path = Path(settings.anomaly_model_path)
    bundle = _load_file(path)
    if bundle is None:
        _simulator = None
        if not _missing_logged:
            logger.error(
                "Modèle absent (%s) : dérive conjointe inactive. Les mesures continuent.",
                path,
            )
            _missing_logged = True
    elif usable_simulator(bundle) is None:
        _simulator = None
        logger.error(
            "Fichier refusé (%s) : dérive conjointe inactive. Les mesures continuent.",
            path,
        )
    else:
        _simulator = bundle
        _missing_logged = False
        logger.info("Loaded simulator couple model from %s", path)
    _room_temp = _load_room(settings.room_temp_path, "temp")
    _room_hum = _load_room(settings.room_hum_path, "hum")
    _room_couple = _load_room(settings.room_couple_path, "couple")


def assess(rows: Sequence) -> Assessment:
    return decide(
        rows,
        simulator_bundle=_simulator,
        room_temp_bundle=_room_temp,
        room_hum_bundle=_room_hum,
        room_couple_bundle=_room_couple,
    )


def _describe(bundle: dict | None, role: str) -> dict:
    if bundle is None:
        return {"loaded": False, "role": role}
    info = bundle.get("info") if isinstance(bundle.get("info"), dict) else {}
    trained_on = info.get("trained_on")
    if trained_on is None and role == "simulator_couple":
        trained_on = "simulator"
    return {
        "loaded": True,
        "role": role,
        "name": info.get("name", "forêt d'isolation"),
        "version": info.get("version"),
        "trained_on": trained_on,
        "channels": info.get("channels"),
    }


def note_window(device: str, assessment: Assessment, now: float | None = None) -> dict:
    """Remember the visitor lines for the screen. Logs only when they change."""
    if assessment.pause != _last_pause.get(device):
        _last_pause[device] = assessment.pause
        if assessment.pause:
            logger.info("%s — %s", device, assessment.pause)
    if assessment.skipped != _last_skip.get(device):
        _last_skip[device] = assessment.skipped
        if assessment.skipped:
            logger.info("%s — %s", device, assessment.skipped)
    line = silence_line(device, now)
    if line != _last_silence.get(device):
        _last_silence[device] = line
        if line:
            logger.info("%s — %s", device, line)
    body = {
        "device": device,
        "joint_drift": assessment.pause or assessment.skipped,
        "silence": silence_line(device, now),
        "models": {
            "couple": _describe(_simulator, "simulator_couple"),
            "room_temp": _describe(_room_temp, "room_temp"),
            "room_hum": _describe(_room_hum, "room_hum"),
            "room_couple": _describe(_room_couple, "room_couple"),
        },
    }
    _status[device] = body
    return body


def scoring_snapshot() -> dict:
    return {"devices": list(_status.values())}
