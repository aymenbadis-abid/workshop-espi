"""Turn one telemetry window into named findings.

No fixed room limit is applied here. 27 °C, 33 °C, and the board gas delta
stay on the firmware. Light is never scored. Gas is not part of the
single-channel room models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.modules.ml.features import (
    FEATURE_NAMES,
    SERIES_FEATURE_NAMES,
    WINDOW,
    feature_vector,
    series_feature_vector,
)
from app.modules.ml.gate import ALERT_COOLDOWN_S, MODEL_ABSENT, OFF_PACE, joint_pause, room_span_ok
from app.modules.ml.phrases import couple_detail, couple_phrase, series_detail, series_phrase


@dataclass(frozen=True)
class Finding:
    key: str
    message: str
    detail: str
    payload: dict


@dataclass(frozen=True)
class Assessment:
    pause: str | None
    findings: tuple[Finding, ...]
    skipped: str | None = None


def _value(row: object, name: str) -> object:
    if isinstance(row, dict):
        return row[name]
    return getattr(row, name)


def _simulated(row: object) -> set[str]:
    raw = _value(row, "simulated") or []
    return {str(item) for item in raw}


def _info(bundle: dict | None) -> dict:
    if not bundle:
        return {}
    info = bundle.get("info")
    return info if isinstance(info, dict) else {}


def _trained_on(bundle: dict | None) -> str:
    if not bundle:
        return ""
    return str(_info(bundle).get("trained_on", "simulator"))


def _channels(bundle: dict | None) -> list[str]:
    raw = _info(bundle).get("channels")
    if raw:
        return [str(item) for item in raw]
    return ["temp", "gas"]


def usable_simulator(bundle: dict | None) -> dict | None:
    """The couple file learned on the simulator. A room file is refused."""
    if bundle is None or _trained_on(bundle) != "simulator":
        return None
    if _channels(bundle) != ["temp", "gas"]:
        return None
    return bundle


def usable_room_couple(bundle: dict | None) -> dict | None:
    if bundle is None or _trained_on(bundle) != "room":
        return None
    if _channels(bundle) != ["temp", "gas"]:
        return None
    return bundle


def usable_series(bundle: dict | None, channel: str) -> dict | None:
    if channel not in {"temp", "hum"}:
        return None
    if bundle is None or _trained_on(bundle) != "room":
        return None
    if _channels(bundle) != [channel]:
        return None
    return bundle


def _named(vector, names: tuple[str, ...]) -> dict[str, float]:
    return {name: float(value) for name, value in zip(names, vector)}


def _anomaly(bundle: dict, vector) -> tuple[bool, dict[str, float]]:
    row = vector.reshape(1, -1)
    scaled = bundle["scaler"].transform(row)[0]
    names = FEATURE_NAMES if len(scaled) == len(FEATURE_NAMES) else SERIES_FEATURE_NAMES
    zscores = {name: float(value) for name, value in zip(names, scaled)}
    info = _info(bundle)
    if "score_threshold" in info:
        score = float(bundle["model"].decision_function(row)[0])
        return score < float(info["score_threshold"]), zscores
    return int(bundle["model"].predict(row)[0]) == -1, zscores


def _payload(bundle: dict, features: dict[str, float], detail: str) -> dict:
    info = _info(bundle)
    return {
        "model": info.get("algorithm", "isolation_forest"),
        "model_name": info.get("name", "forêt d'isolation"),
        "version": info.get("version", "simulator-couple"),
        "trained_on": _trained_on(bundle),
        "channels": _channels(bundle),
        "detail": detail,
        "features": features,
        "cooldown_s": int(ALERT_COOLDOWN_S),
    }


def _window(rows: Sequence) -> list:
    items = list(rows)
    if len(items) < WINDOW:
        return items
    return items[-WINDOW:]


def decide(
    rows: Sequence,
    *,
    simulator_bundle: dict | None,
    room_temp_bundle: dict | None = None,
    room_hum_bundle: dict | None = None,
    room_couple_bundle: dict | None = None,
) -> Assessment:
    """Score a window. Oldest reading first. Mixed channels never reach a model."""
    window = _window(rows)
    if len(window) < WINDOW:
        return Assessment(None, ())

    flags = [("temp" in _simulated(row), "gas" in _simulated(row)) for row in window]
    room_couple = usable_room_couple(room_couple_bundle)
    pause = joint_pause(flags, room_couple_ready=room_couple is not None)
    findings: list[Finding] = []
    skipped: str | None = None
    both_real = all(not temp and not gas for temp, gas in flags)

    if pause is None:
        bundle = room_couple if both_real else usable_simulator(simulator_bundle)
        if bundle is None:
            skipped = MODEL_ABSENT
        elif both_real and not room_span_ok([int(_value(row, "ts")) for row in window]):
            skipped = OFF_PACE
        else:
            samples = [(float(_value(row, "temp")), float(_value(row, "gas"))) for row in window]
            vector = feature_vector(samples)
            anomalous, zscores = _anomaly(bundle, vector)
            if anomalous:
                features = _named(vector, FEATURE_NAMES)
                detail = couple_detail(features)
                findings.append(
                    Finding(
                        key="couple",
                        message=couple_phrase(features, zscores),
                        detail=detail,
                        payload=_payload(bundle, features, detail),
                    )
                )

    timestamps = [int(_value(row, "ts")) for row in window]
    span_ok = room_span_ok(timestamps)
    for channel, bundle in (("temp", room_temp_bundle), ("hum", room_hum_bundle)):
        usable = usable_series(bundle, channel)
        if usable is None:
            continue
        if not all(channel not in _simulated(row) for row in window):
            continue
        if not span_ok:
            skipped = skipped or OFF_PACE
            continue
        vector = series_feature_vector([float(_value(row, channel)) for row in window])
        anomalous, zscores = _anomaly(usable, vector)
        if not anomalous:
            continue
        stats = _named(vector, SERIES_FEATURE_NAMES)
        detail = series_detail(channel, stats)
        findings.append(
            Finding(
                key=channel,
                message=series_phrase(channel, zscores),
                detail=detail,
                payload=_payload(usable, stats, detail),
            )
        )

    return Assessment(pause, tuple(findings), skipped)
