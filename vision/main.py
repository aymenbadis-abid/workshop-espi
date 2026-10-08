"""Person detection on the host camera.

Docker cannot see the laptop camera, so this process stays on the host.
It resizes frames to 640x480, runs YOLOv8n with ByteTrack, posts one arrival
and one departure, and serves an MJPEG stream. This file does not start
itself on import. A heavier weight and a pose check are not enabled.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import requests
from ultralytics import YOLO

from presence import (
    FRAME_SIZE,
    INFER_INTERVAL_S,
    MIN_CONFIDENCE,
    Detection,
    PresenceTracker,
    ids_in_zone,
    parse_zone,
    zone_pixels,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("vision")

PERSON_CLASS = 0
ROOT = Path(__file__).resolve().parents[1]


class FrameHub:
    def __init__(self) -> None:
        self._jpeg = b""
        self._condition = threading.Condition()

    def publish(self, jpeg: bytes) -> None:
        with self._condition:
            self._jpeg = jpeg
            self._condition.notify_all()

    def latest(self) -> bytes:
        with self._condition:
            self._condition.wait(timeout=1.0)
            return self._jpeg


hub = FrameHub()


class ImageLoop:
    """Repeat a still image so a photo can stand in for a camera."""

    def __init__(self, path: Path) -> None:
        self._frame = cv2.imread(str(path))
        if self._frame is None:
            raise RuntimeError(f"Cannot read image {path}")

    def isOpened(self) -> bool:
        return True

    def read(self) -> tuple[bool, object]:
        time.sleep(0.1)
        return True, self._frame.copy()

    def release(self) -> None:
        return None


def open_source(source: str):
    path = Path(source)
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"}:
        return ImageLoop(path)
    if source.isdigit():
        return cv2.VideoCapture(int(source))
    return cv2.VideoCapture(source)


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def post_alert(api_url: str, message: str, kind: str, track_id: int) -> None:
    response = requests.post(
        f"{api_url.rstrip('/')}/api/v1/alerts",
        json={
            "device": "camera",
            "type": "person",
            "message": message,
            "severity": "warning",
            "payload": {"model": "YOLOv8n", "event": kind, "track_id": track_id},
        },
        timeout=5,
    )
    response.raise_for_status()


def detections_from(result) -> list[Detection]:
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    confidences = boxes.conf.cpu().numpy()
    identifiers = None if boxes.id is None else boxes.id.cpu().numpy()
    found: list[Detection] = []
    for index in range(len(xyxy)):
        track_id = None if identifiers is None else int(identifiers[index])
        x1, y1, x2, y2 = (float(value) for value in xyxy[index])
        found.append(Detection(x1, y1, x2, y2, float(confidences[index]), track_id))
    return found


def draw_kept(frame, detections: list[Detection], zone_px: tuple[float, float, float, float]):
    annotated = frame.copy()
    x1, y1, x2, y2 = (int(value) for value in zone_px)
    cv2.rectangle(annotated, (x1, y1), (x2, y2), (180, 180, 180), 1)
    for detection in detections:
        if detection.track_id is None:
            continue
        cv2.rectangle(
            annotated,
            (int(detection.x1), int(detection.y1)),
            (int(detection.x2), int(detection.y2)),
            (80, 220, 120),
            2,
        )
    return annotated


def capture_loop(source: str, model: YOLO, api_url: str, zone_raw: str | None) -> None:
    camera = open_source(source)
    if not camera.isOpened():
        raise RuntimeError(f"Cannot open video source {source}")
    tracker = PresenceTracker()
    zone_px = zone_pixels(FRAME_SIZE, parse_zone(zone_raw))
    last_infer = 0.0
    annotated = None
    missing_id_logged = False
    while True:
        ok, frame = camera.read()
        if not ok:
            if source.isdigit():
                time.sleep(0.2)
                continue
            camera.release()
            camera = open_source(source)
            continue
        frame = cv2.resize(frame, FRAME_SIZE)
        now = time.monotonic()
        if now - last_infer >= INFER_INTERVAL_S:
            last_infer = now
            started = time.perf_counter()
            results = model.track(
                frame,
                persist=True,
                classes=[PERSON_CLASS],
                conf=MIN_CONFIDENCE,
                tracker="bytetrack.yaml",
                verbose=False,
                imgsz=480,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            detections = detections_from(results[0])
            kept_ids = ids_in_zone(detections, zone_px)
            if not missing_id_logged and any(
                item.track_id is None and item.confidence >= MIN_CONFIDENCE for item in detections
            ):
                logger.info("A person box has no track id; no arrival is posted for it")
                missing_id_logged = True
            logger.info("inference %.1f ms, persons=%s", latency_ms, len(kept_ids))
            annotated = draw_kept(
                frame,
                [item for item in detections if item.track_id in kept_ids],
                zone_px,
            )
            for event in tracker.update(kept_ids, now):
                try:
                    post_alert(api_url, event.message, event.kind, event.track_id)
                    logger.info("Person %s posted for track %s", event.kind, event.track_id)
                except requests.RequestException as exc:
                    logger.warning("Alert post failed: %s", exc)
        shown = frame if annotated is None else annotated
        ok_jpeg, encoded = cv2.imencode(".jpg", shown, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok_jpeg:
            hub.publish(encoded.tobytes())


class StreamHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?", 1)[0] not in {"/stream", "/"}:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            while True:
                jpeg = hub.latest()
                if not jpeg:
                    continue
                self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                self.wfile.write(jpeg)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            return

    def log_message(self, fmt: str, *args) -> None:
        logger.debug(fmt, *args)


def main() -> None:
    load_env(ROOT / ".env")
    source = os.environ.get("VIDEO_SOURCE", "0")
    api_url = os.environ.get("VISION_API_URL", "http://127.0.0.1:8000")
    port = int(os.environ.get("VISION_PORT", "8090"))
    weights = Path(os.environ.get("YOLO_WEIGHTS", ROOT / "vision" / "weights" / "yolov8n.pt"))
    weights.parent.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(weights))
    threading.Thread(
        target=capture_loop,
        args=(source, model, api_url, os.environ.get("VISION_ZONE")),
        daemon=True,
    ).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), StreamHandler)
    logger.info("MJPEG stream on port %s, source %s", port, source)
    server.serve_forever()


if __name__ == "__main__":
    main()
