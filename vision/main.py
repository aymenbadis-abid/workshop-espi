"""Person detection on the host camera.

Docker cannot see the laptop camera, so this process stays on the host.
It resizes every frame to 640x480, runs YOLOv8n, logs inference latency,
posts an alert, and serves an MJPEG stream for the dashboard.
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("vision")

FRAME_SIZE = (640, 480)
PERSON_CLASS = 0
ALERT_COOLDOWN_S = 8.0
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


def post_alert(api_url: str) -> None:
    response = requests.post(
        f"{api_url.rstrip('/')}/api/v1/alerts",
        json={
            "device": "camera",
            "type": "person",
            "message": "Personne détectée devant la caméra",
            "severity": "warning",
        },
        timeout=5,
    )
    response.raise_for_status()


def capture_loop(source: str, model: YOLO, api_url: str) -> None:
    camera = open_source(source)
    if not camera.isOpened():
        raise RuntimeError(f"Cannot open video source {source}")
    last_alert = 0.0
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
        started = time.perf_counter()
        results = model.predict(frame, classes=[PERSON_CLASS], verbose=False, imgsz=480)
        latency_ms = (time.perf_counter() - started) * 1000.0
        boxes = results[0].boxes
        count = 0 if boxes is None else len(boxes)
        logger.info("inference %.1f ms, persons=%s", latency_ms, count)
        annotated = results[0].plot()
        ok_jpeg, encoded = cv2.imencode(".jpg", annotated, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok_jpeg:
            hub.publish(encoded.tobytes())
        now = time.monotonic()
        if count > 0 and now - last_alert >= ALERT_COOLDOWN_S:
            try:
                post_alert(api_url)
                last_alert = now
                logger.info("Person alert posted")
            except requests.RequestException as exc:
                logger.warning("Alert post failed: %s", exc)


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
    threading.Thread(target=capture_loop, args=(source, model, api_url), daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", port), StreamHandler)
    logger.info("MJPEG stream on port %s, source %s", port, source)
    server.serve_forever()


if __name__ == "__main__":
    main()
