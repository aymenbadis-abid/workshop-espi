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
from app.modules.ml.service import score, should_emit
from app.modules.telemetry.schemas import StatusIn, StatusOut, TelemetryIn, TelemetryOut
from app.modules.telemetry.service import recent_device_window, record_telemetry, upsert_status

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


async def _handle(topic: str, raw: dict) -> None:
    base = settings.mqtt_topic_base.rstrip("/")
    async with SessionLocal() as session:
        if topic == f"{base}/telemetry":
            payload = TelemetryIn.model_validate(raw)
            row = await record_telemetry(session, payload)
            body = TelemetryOut.model_validate(row).model_dump(mode="json")
            await hub.broadcast({"kind": "telemetry", "data": body})
            await _score_window(session, payload.device)
        elif topic == f"{base}/alerts":
            payload = AlertCreate.model_validate(_normalize_alert(raw))
            row = await create_alert(session, payload, source="mqtt")
            body = AlertOut.model_validate(row).model_dump(mode="json")
            await hub.broadcast({"kind": "alert", "data": body})
        elif topic == f"{base}/status":
            payload = StatusIn.model_validate(raw)
            row = await upsert_status(session, payload)
            body = StatusOut.model_validate(row).model_dump(mode="json")
            await hub.broadcast({"kind": "status", "data": body})
        else:
            logger.warning("Ignored MQTT topic %s", topic)


async def _score_window(session, device: str) -> None:
    rows = await recent_device_window(session, device, 30)
    samples = [(row.temp, row.gas) for row in rows]
    if not score(samples) or not should_emit(device):
        return
    alert = AlertCreate(
        device=device,
        type="anomaly",
        message="Dérive détectée : température et gaz montent ensemble",
        severity="warning",
        ts=rows[-1].ts,
        payload={"model": "isolation_forest"},
    )
    stored = await create_alert(session, alert, source="ml")
    body = AlertOut.model_validate(stored).model_dump(mode="json")
    await hub.broadcast({"kind": "alert", "data": body})
    logger.info("Anomaly alert for %s", device)


async def _consume_once() -> None:
    base = settings.mqtt_topic_base.rstrip("/")
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
        await client.subscribe(f"{base}/telemetry")
        await client.subscribe(f"{base}/alerts")
        await client.subscribe(f"{base}/status")
        logger.info("MQTT connected to %s:%s", settings.mqtt_host, settings.mqtt_port)
        async for message in client.messages:
            topic = _topic_name(message.topic)
            try:
                raw = json.loads(message.payload)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                logger.warning("Invalid JSON on %s: %s", topic, exc)
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
