"""Arrival and departure of one person at the room entrance.

The lightweight detector still proposes boxes. This module keeps a box only
when it is clear and large enough, and only when its center is inside the
entrance. The same person produces one arrival and, later, one departure.
"""

from __future__ import annotations

from dataclasses import dataclass

FRAME_SIZE = (640, 480)
ENTRANCE_NORM = (0.18, 0.15, 0.82, 0.98)
MIN_CONFIDENCE = 0.5
MIN_HEIGHT = 80.0
INFER_INTERVAL_S = 0.25

ARRIVAL_MESSAGE = "Une personne est arrivée dans la salle"
DEPARTURE_MESSAGE = "Une personne est partie de la salle"


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    track_id: int | None = None


@dataclass(frozen=True)
class PresenceEvent:
    kind: str
    track_id: int
    message: str


def parse_zone(raw: str | None) -> tuple[float, float, float, float]:
    """Read `x1,y1,x2,y2` fractions. An empty value keeps the entrance rectangle."""
    if raw is None or not raw.strip():
        return ENTRANCE_NORM
    parts = [float(item) for item in raw.split(",")]
    if len(parts) != 4:
        raise ValueError(f"Entrance zone needs four numbers, got {raw!r}")
    return (parts[0], parts[1], parts[2], parts[3])


def zone_pixels(
    frame_size: tuple[int, int],
    norm: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    width, height = frame_size
    nx1, ny1, nx2, ny2 = norm
    return (nx1 * width, ny1 * height, nx2 * width, ny2 * height)


def accept_detection(detection: Detection) -> bool:
    """Drop a weak score or a box too small to be a person near the entrance."""
    height = detection.y2 - detection.y1
    return detection.confidence >= MIN_CONFIDENCE and height >= MIN_HEIGHT


def _center_inside(detection: Detection, zone: tuple[float, float, float, float]) -> bool:
    cx = (detection.x1 + detection.x2) / 2.0
    cy = (detection.y1 + detection.y2) / 2.0
    x1, y1, x2, y2 = zone
    return x1 <= cx <= x2 and y1 <= cy <= y2


def ids_in_zone(detections: list[Detection], zone: tuple[float, float, float, float]) -> set[int]:
    found: set[int] = set()
    for detection in detections:
        if detection.track_id is None or not accept_detection(detection):
            continue
        if _center_inside(detection, zone):
            found.add(detection.track_id)
    return found


class PresenceTracker:
    """One arrival when a person enters the zone, one departure after they leave."""

    def __init__(self, grace_s: float = 2.0) -> None:
        self.grace_s = grace_s
        self._present: set[int] = set()
        self._missing_since: dict[int, float] = {}

    def update(self, ids: set[int], now: float) -> list[PresenceEvent]:
        events: list[PresenceEvent] = []
        for track_id in sorted(ids):
            self._missing_since.pop(track_id, None)
            if track_id in self._present:
                continue
            self._present.add(track_id)
            events.append(PresenceEvent("arrival", track_id, ARRIVAL_MESSAGE))
        for track_id in sorted(self._present):
            if track_id in ids:
                continue
            if track_id not in self._missing_since:
                self._missing_since[track_id] = now
            if now - self._missing_since[track_id] < self.grace_s:
                continue
            self._present.discard(track_id)
            self._missing_since.pop(track_id, None)
            events.append(PresenceEvent("departure", track_id, DEPARTURE_MESSAGE))
        return events
