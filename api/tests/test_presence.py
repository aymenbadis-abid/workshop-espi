"""Arrival, departure, confidence and entrance zone. The camera stays closed."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "vision"))

from presence import (  # noqa: E402
    ARRIVAL_MESSAGE,
    DEPARTURE_MESSAGE,
    FRAME_SIZE,
    Detection,
    PresenceTracker,
    accept_detection,
    ids_in_zone,
    zone_pixels,
)

ZONE = zone_pixels(FRAME_SIZE, (0.18, 0.15, 0.82, 0.98))


def _person(x1: float, y1: float, size: float = 120.0, confidence: float = 0.8, track_id: int | None = 1) -> Detection:
    return Detection(x1, y1, x1 + size * 0.6, y1 + size, confidence, track_id)


def test_weak_or_tiny_boxes_are_dropped() -> None:
    weak = _person(200, 120, confidence=0.4)
    tiny = _person(200, 120, size=40, confidence=0.9)
    clear = _person(200, 120, confidence=0.8)
    assert accept_detection(weak) is False
    assert accept_detection(tiny) is False
    assert accept_detection(clear) is True
    assert ids_in_zone([weak, tiny, clear], ZONE) == {1}


def test_outside_the_entrance_posts_nothing() -> None:
    edge = _person(0, 200, track_id=7)
    assert ids_in_zone([edge], ZONE) == set()
    tracker = PresenceTracker()
    assert tracker.update(ids_in_zone([edge], ZONE), now=0.0) == []


def test_arrival_then_departure_without_a_repeat() -> None:
    tracker = PresenceTracker(grace_s=1.0)
    inside = {1}
    first = tracker.update(inside, now=0.0)
    assert [event.kind for event in first] == ["arrival"]
    assert first[0].message == ARRIVAL_MESSAGE
    assert tracker.update(inside, now=0.5) == []
    assert tracker.update(inside, now=4.0) == []
    assert tracker.update(set(), now=4.5) == []
    left = tracker.update(set(), now=6.0)
    assert [event.kind for event in left] == ["departure"]
    assert left[0].message == DEPARTURE_MESSAGE
    again = tracker.update({1}, now=7.0)
    assert [event.kind for event in again] == ["arrival"]


def test_two_people_leave_one_at_a_time() -> None:
    tracker = PresenceTracker(grace_s=1.0)
    entered = tracker.update({1, 2}, now=0.0)
    assert [event.kind for event in entered] == ["arrival", "arrival"]
    assert tracker.update({2}, now=0.2) == []
    left = tracker.update({2}, now=1.3)
    assert [(event.kind, event.track_id) for event in left] == [("departure", 1)]
    assert tracker.update({2}, now=3.0) == []


if __name__ == "__main__":
    test_weak_or_tiny_boxes_are_dropped()
    test_outside_the_entrance_posts_nothing()
    test_arrival_then_departure_without_a_repeat()
    test_two_people_leave_one_at_a_time()
    print("presence checks ok")
