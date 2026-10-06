"""Publish a dashboard command on the device command topic."""

from __future__ import annotations

import json
import ssl

import aiomqtt

from app.core.config import settings
from app.modules.commands.schemas import CommandIn
from app.mqtt.payloads import device_command_text


def command_payload(body: CommandIn) -> dict:
    if body.scenario is not None:
        return {"scenario": body.scenario}
    return {"target": body.target, "state": body.state}


async def publish_command(body: CommandIn) -> str:
    """Publish the plain command the ESP32 reads, and JSON for the simulator.

    LED and scenario JSON stay on the simulator topic so a demo without the
    board still moves. Buzzer and auto exist only on the board.
    """
    device_base = settings.mqtt_device_base.rstrip("/")
    simulator_base = settings.mqtt_topic_base.rstrip("/")
    device_topic = f"{device_base}/cmd"
    text = device_command_text(body.auto, body.scenario, body.target, body.state)
    tls_params = aiomqtt.TLSParameters(
        ca_certs=settings.mqtt_ca_cert,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    async with aiomqtt.Client(
        hostname=settings.mqtt_host,
        port=settings.mqtt_port,
        username=settings.mqtt_api_username,
        password=settings.mqtt_api_password,
        identifier="sentinelx-api-cmd",
        tls_params=tls_params,
        tls_insecure=False,
    ) as client:
        await client.publish(device_topic, text, qos=1)
        simulator_hears = body.scenario is not None or body.target in {"led_red", "led_green"}
        if simulator_hears and simulator_base != device_base:
            topic = f"{simulator_base}/cmd"
            await client.publish(topic, json.dumps(command_payload(body)), qos=1)
    return device_topic
