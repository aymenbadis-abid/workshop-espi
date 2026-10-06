"""Publish a dashboard command on the device command topic."""

from __future__ import annotations

import json
import ssl

import aiomqtt

from app.core.config import settings
from app.modules.commands.schemas import CommandIn


def command_payload(body: CommandIn) -> dict:
    if body.scenario is not None:
        return {"scenario": body.scenario}
    return {"target": body.target, "state": body.state}


async def publish_command(body: CommandIn) -> str:
    topic = f"{settings.mqtt_topic_base.rstrip('/')}/cmd"
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
        await client.publish(topic, json.dumps(command_payload(body)), qos=1)
    return topic
