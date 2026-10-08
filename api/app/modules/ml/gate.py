"""Decide when the temperature-gas couple may be scored.

The simulator model learned a fictional room near 24 °C with gas near 300.
A real temperature next to simulated gas is not that signature. Real gas is
scored only by a model trained on this room, never by the simulator model.
"""

from __future__ import annotations

import time
from typing import Sequence

from app.modules.ml.features import WINDOW

SIMULATED_GAS = "Gaz simulé : dérive conjointe inactive"
REAL_GAS_NO_ROOM = "Gaz réel, modèle de salle absent : dérive conjointe inactive"
MODEL_ABSENT = "Modèle absent : dérive conjointe inactive"
OFF_PACE = "Rythme hors carte : dérive inactive"
ALERT_COOLDOWN_S = 120.0

# Thirty board readings at 5 s span 145 s. Room models skip any other pace.
ROOM_SPAN_MIN_S = 100
ROOM_SPAN_MAX_S = 200


def joint_pause(flags: list[tuple[bool, bool]], *, room_couple_ready: bool) -> str | None:
    """Return the visitor sentence when the couple must stay silent.

    `flags` holds `(temperature_is_simulated, gas_is_simulated)`, oldest first.
    None means the couple may be scored.
    """
    if len(flags) < WINDOW:
        return None
    window = flags[-WINDOW:]
    temp_simulated = {temp for temp, _gas in window}
    gas_simulated = {gas for _temp, gas in window}
    both_simulated = temp_simulated == {True} and gas_simulated == {True}
    both_real = temp_simulated == {False} and gas_simulated == {False}
    if both_simulated:
        return None
    if both_real and room_couple_ready:
        return None
    if True in gas_simulated:
        return SIMULATED_GAS
    return REAL_GAS_NO_ROOM


def room_span_ok(timestamps: list[int]) -> bool:
    """True when the window covers about two and a half minutes at the board pace."""
    if len(timestamps) < WINDOW:
        return False
    span = int(timestamps[-1]) - int(timestamps[0])
    return ROOM_SPAN_MIN_S <= span <= ROOM_SPAN_MAX_S


def _row_ts(row: object) -> int:
    if isinstance(row, dict):
        return int(row["ts"])
    return int(row.ts)


def paced_rows(rows: Sequence, step_s: int = 5, window: int = WINDOW) -> list:
    """Keep a 5 s grid so a faster live feed still scores a 2 min 30 window.

    The dashboard may store a point every 2 s. The room models stay on the
    board pace: thirty kept points still cover about two and a half minutes.
    """
    chosen: list = []
    last: int | None = None
    for row in rows:
        ts = _row_ts(row)
        if last is None or ts - last >= step_s:
            chosen.append(row)
            last = ts
    if len(chosen) > window:
        return chosen[-window:]
    return chosen


_last_alert_at: dict[str, float] = {}


def _token(device: str, key: str) -> str:
    return f"{device}:{key}"


def should_emit(device: str, key: str, now: float | None = None) -> bool:
    """Limit repeat findings while the same shape is still in progress."""
    moment = time.monotonic() if now is None else now
    token = _token(device, key)
    previous = _last_alert_at.get(token)
    if previous is not None and moment - previous < ALERT_COOLDOWN_S:
        return False
    _last_alert_at[token] = moment
    return True


def silence_line(device: str, now: float | None = None) -> str | None:
    """Visitor line while a finding is being held back for two minutes."""
    from app.modules.ml.phrases import SILENCE_LINE

    moment = time.monotonic() if now is None else now
    for key in ("couple", "temp", "hum"):
        previous = _last_alert_at.get(_token(device, key))
        if previous is not None and moment - previous < ALERT_COOLDOWN_S:
            return SILENCE_LINE
    return None
