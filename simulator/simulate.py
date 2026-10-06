"""Publish the Sentinel-X MQTT contract over MQTTS.

The script stands in for the NodeMCU: same topics, same JSON, same account.
Run it from the repository root after Mosquitto is up:

    python simulator/simulate.py
"""

from __future__ import annotations

import json
import os
import random
import ssl
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from scenario import ScenarioEngine

ROOT = Path(__file__).resolve().parents[1]
DEVICE = "esp01"


def load_env(path: Path) -> None:
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None or value == "":
        print(f"Missing {name}. Copy .env.example to .env.", file=sys.stderr)
        sys.exit(1)
    return value


def main() -> None:
    load_env(ROOT / ".env")
    topic_base = env("MQTT_TOPIC_BASE", "sentinelx/g6")
    host = env("MQTT_PUBLIC_HOST", "127.0.0.1")
    port = int(env("MQTT_PORT", "8883"))
    username = env("MQTT_USERNAME")
    password = env("MQTT_PASSWORD")
    ca_cert = env("MQTT_CA_CERT", "infra/certs/ca.crt")
    ca_path = Path(ca_cert)
    if not ca_path.is_absolute():
        ca_path = ROOT / ca_path
    if not ca_path.is_file():
        print(f"CA certificate not found: {ca_path}", file=sys.stderr)
        sys.exit(1)

    telemetry_topic = f"{topic_base}/telemetry"
    alerts_topic = f"{topic_base}/alerts"
    status_topic = f"{topic_base}/status"
    cmd_topic = f"{topic_base}/cmd"

    engine = ScenarioEngine()
    started = time.monotonic()
    max_messages = int(os.environ.get("SIM_MAX_MESSAGES", "0"))
    sent = 0

    offline = json.dumps({"device": DEVICE, "online": False, "ip": "simulator", "uptime": 0})

    def publish_status(client: mqtt.Client, online: bool) -> None:
        uptime = int(time.monotonic() - started)
        payload = json.dumps(
            {"device": DEVICE, "online": online, "ip": "simulator", "uptime": uptime}
        )
        client.publish(status_topic, payload, qos=1, retain=True)

    def on_connect(client: mqtt.Client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure if hasattr(reason_code, "is_failure") else reason_code != 0:
            print(f"MQTT connect failed: {reason_code}", file=sys.stderr)
            return
        client.subscribe(cmd_topic, qos=1)
        publish_status(client, True)
        print(f"Connected to {host}:{port}, subscribed to {cmd_topic}")

    def on_message(client: mqtt.Client, userdata, message: mqtt.MQTTMessage) -> None:
        try:
            body = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"Ignored command: {exc}", file=sys.stderr)
            return
        if "scenario" in body:
            try:
                previous = engine.scenario
                engine.set_scenario(str(body["scenario"]))
            except ValueError as exc:
                print(exc, file=sys.stderr)
                return
            print(f"Scenario is now {engine.scenario}")
            if engine.scenario == "gas_leak" and previous != "gas_leak":
                alert = {
                    "device": DEVICE,
                    "ts": int(time.time()),
                    "type": "gas_leak",
                    "message": "Pic de gaz simulé",
                    "severity": "critical",
                }
                client.publish(alerts_topic, json.dumps(alert), qos=1)
        if "target" in body and "state" in body:
            print(f"LED command (no hardware in the simulator): {body['target']}={body['state']}")

    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id="sentinelx-simulator",
    )
    client.username_pw_set(username, password)
    client.tls_set(ca_certs=str(ca_path), tls_version=ssl.PROTOCOL_TLS_CLIENT)
    client.tls_insecure_set(False)
    client.will_set(status_topic, offline, qos=1, retain=True)
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(host, port, keepalive=30)
    client.loop_start()

    try:
        while max_messages == 0 or sent < max_messages:
            delay = random.uniform(2.0, 5.0)
            if max_messages:
                delay = min(delay, 0.4)
            time.sleep(delay)
            sample = engine.step(delay)
            payload = {
                "device": DEVICE,
                "ts": int(time.time()),
                "temp": sample.temp,
                "hum": sample.hum,
                "gas": sample.gas,
                "light": sample.light,
                "simulated": sample.simulated,
            }
            client.publish(telemetry_topic, json.dumps(payload), qos=0)
            sent += 1
            print(
                f"{engine.scenario} temp={sample.temp} hum={sample.hum} "
                f"gas={sample.gas} light={sample.light}"
            )
    except KeyboardInterrupt:
        print("Stopping simulator.")
    finally:
        publish_status(client, False)
        time.sleep(0.3)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
