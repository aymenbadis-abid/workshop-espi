"""Subscribe to device topics and store what they publish.

Reconnects with a capped backoff. A bad payload is logged and skipped so one
corrupt message cannot stop ingestion.
"""

from __future__ import annotations

import asyncio
import json
import logging
import ssl

import aiomqtt
from pydantic import ValidationError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.hub import hub
from app.modules.alerts.schemas import AlertCreate, AlertOut
from app.modules.alerts.service import create_alert
from app.modules.ml.gate import paced_rows
from app.modules.ml.service import assess, note_window, should_emit
from app.modules.telemetry.schemas import StatusIn, StatusOut, TelemetryIn, TelemetryOut
from app.modules.telemetry.service import recent_device_window, record_telemetry, upsert_status
from app.mqtt.payloads import classify_topic, normalize_telemetry, parse_ack, parse_plain_status

logger = logging.getLogger(__name__)


def _topic_name(topic: object) -> str:
    if isinstance(topic, bytes):
        return topic.decode("utf-8")
    return str(topic)


def _normalize_alert(raw: dict) -> dict:
    data = dict(raw)
    if "type" not in data and "alert" in data:
        data["type"] = str(data.pop("alert"))
    if "message" not in data and "type" in data:
        data["message"] = str(data["type"])
    data.setdefault("payload", {})
    return data


def _bases() -> tuple[str, str]:
    return settings.mqtt_topic_base, settings.mqtt_device_base


async def _handle(topic: str, raw: dict) -> None:
    classified = classify_topic(topic, *_bases())
    if classified is None:
        logger.warning("Ignored MQTT topic %s", topic)
        return
    kind, device_hint = classified
    device_to_score = None
    async with SessionLocal() as session:
        if kind == "telemetry":
            payload = TelemetryIn.model_validate(normalize_telemetry(raw, device_hint))
            row = await record_telemetry(session, payload)
            body = TelemetryOut.model_validate(row).model_dump(mode="json")
            await hub.broadcast({"kind": "telemetry", "data": body})
            device_to_score = payload.device
        elif kind == "alerts":
            if device_hint and "device" not in raw:
                raw = {**raw, "device": device_hint}
            payload = AlertCreate.model_validate(_normalize_alert(raw))
            row = await create_alert(session, payload, source="mqtt")
            body = AlertOut.model_validate(row).model_dump(mode="json")
            await hub.broadcast({"kind": "alert", "data": body})
        elif kind == "status":
            if device_hint and "device" not in raw:
                raw = {**raw, "device": device_hint}
            payload = StatusIn.model_validate(raw)
            row = await upsert_status(session, payload)
            body = StatusOut.model_validate(row).model_dump(mode="json")
            await hub.broadcast({"kind": "status", "data": body})
        elif kind == "ack":
            logger.warning("Ack topic %s carried a JSON object, expected text", topic)
    # The model runs after the measure is already on the socket. The next
    # packet is not held behind that score.
    if device_to_score:
        _schedule_score(device_to_score)


async def _handle_text(topic: str, text: str) -> None:
    classified = classify_topic(topic, *_bases())
    if classified is None:
        logger.warning("Ignored MQTT topic %s", topic)
        return
    kind, device_hint = classified
    if kind == "ack":
        if not device_hint:
            logger.warning("Ack on %s has no device id", topic)
            return
        payload = AlertCreate.model_validate(parse_ack(text, device_hint))
        async with SessionLocal() as session:
            row = await create_alert(session, payload, source="mqtt")
            body = AlertOut.model_validate(row).model_dump(mode="json")
        await hub.broadcast({"kind": "alert", "data": body})
        return
    if kind == "status" and device_hint:
        payload = StatusIn.model_validate(parse_plain_status(text, device_hint))
        async with SessionLocal() as session:
            row = await upsert_status(session, payload)
            body = StatusOut.model_validate(row).model_dump(mode="json")
        await hub.broadcast({"kind": "status", "data": body})
        return
    raise ValueError(f"Text payload is not valid on {topic}")


_score_locks: dict[str, asyncio.Lock] = {}
_score_pending: set[str] = set()


def _schedule_score(device: str) -> None:
    lock = _score_locks.setdefault(device, asyncio.Lock())
    if lock.locked():
        _score_pending.add(device)
        return
    asyncio.create_task(_score_until_quiet(device, lock))


async def _score_until_quiet(device: str, lock: asyncio.Lock) -> None:
    async with lock:
        while True:
            _score_pending.discard(device)
            try:
                async with SessionLocal() as session:
                    await _score_window(session, device)
            except Exception:
                logger.exception("Scoring failed for %s", device)
            if device not in _score_pending:
                return


async def _score_window(session, device: str) -> None:
    # Six times the window covers a 2 s feed resampled onto the 5 s grid.
    rows = await recent_device_window(session, device, 180)
    assessment = assess(paced_rows(rows))
    for finding in assessment.findings:
        if not should_emit(device, finding.key):
            continue
        alert = AlertCreate(
            device=device,
            type="anomaly",
            message=finding.message,
            severity="warning",
            ts=rows[-1].ts,
            payload=finding.payload,
        )
        stored = await create_alert(session, alert, source="ml")
        body = AlertOut.model_validate(stored).model_dump(mode="json")
        await hub.broadcast({"kind": "alert", "data": body})
        logger.info("Sensor finding for %s: %s", device, finding.message)
    scoring = note_window(device, assessment)
    await hub.broadcast({"kind": "scoring", "data": scoring})


async def _consume_once() -> None:
    simulator_base = settings.mqtt_topic_base.rstrip("/")
    device_base = settings.mqtt_device_base.rstrip("/")
    topics = [
        f"{simulator_base}/telemetry",
        f"{simulator_base}/alerts",
        f"{simulator_base}/status",
    ]
    if device_base != simulator_base:
        topics.extend(
            [
                f"{device_base}/telemetry",
                f"{device_base}/alerts",
                f"{device_base}/status",
                f"{device_base}/ack",
            ]
        )
    tls_params = aiomqtt.TLSParameters(
        ca_certs=settings.mqtt_ca_cert,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    async with aiomqtt.Client(
        hostname=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_api_username,
        password=settings.mqtt_api_password,
        identifier="sentinelx-api",
        tls_params=tls_params,
        tls_insecure=False,
    ) as client:
        for topic in topics:
            await client.subscribe(topic)
        logger.info("MQTT connected to %s:%s", settings.mqtt_host, settings.mqtt_port)
        async for message in client.messages:
            topic = _topic_name(message.topic)
            payload = message.payload
            if isinstance(payload, bytes):
                text = payload.decode("utf-8", errors="replace")
            else:
                text = str(payload)
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                try:
                    await _handle_text(topic, text)
                except (ValidationError, ValueError) as exc:
                    logger.warning("Rejected text on %s: %s", topic, exc)
                continue
            if not isinstance(raw, dict):
                logger.warning("JSON on %s is not an object", topic)
                continue
            try:
                await _handle(topic, raw)
            except ValidationError as exc:
                logger.warning("Rejected payload on %s: %s", topic, exc)


async def mqtt_loop() -> None:
    delay = 1
    while True:
        try:
            await _consume_once()
            delay = 1
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("MQTT session ended; retrying in %ss", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)
