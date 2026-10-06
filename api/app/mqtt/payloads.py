"""Translate the ESP32 wire format into the API models.

The board publishes on sentinelx/esp32-01/*. Commands toward the board are
plain strings (led_red:1, buzzer:0, auto, scenario:drift). The Python
simulator keeps the JSON contract on sentinelx/g6.
"""

from __future__ import annotations

import time

_KINDS = frozenset({"telemetry", "alerts", "status", "ack"})


def classify_topic(topic: str, simulator_base: str, device_base: str) -> tuple[str, str | None] | None:
    """Return the topic kind and, for the board, the device id encoded in the path."""
    checked: list[tuple[str, bool]] = []
    device_base = device_base.rstrip("/")
    simulator_base = simulator_base.rstrip("/")
    if device_base:
        checked.append((device_base, True))
    if simulator_base and simulator_base != device_base:
        checked.append((simulator_base, False))
    for base, hinted in checked:
        prefix = base + "/"
        if not topic.startswith(prefix):
            continue
        kind = topic[len(prefix) :]
        if kind not in _KINDS:
            return None
        device = base.split("/")[-1] if hinted else None
        return kind, device
    return None


def normalize_telemetry(raw: dict, device_hint: str | None = None) -> dict:
    """Fill the fields the dashboard stores when the board omits them.

    A payload that already matches the simulator contract is returned unchanged
    apart from numeric coercion. light_dark without light becomes a chart value.
    Missing temp, hum, or gas are neutral baselines and marked simulated.
    """
    data = dict(raw)
    if device_hint and not data.get("device"):
        data["device"] = device_hint
    if "ts" not in data:
        data["ts"] = int(time.time())
    else:
        data["ts"] = int(data["ts"])

    invented: list[str] = []
    if "light" not in data and "light_dark" in data:
        dark = int(data["light_dark"]) != 0
        data["light"] = 80.0 if dark else 640.0
    for name, baseline in (("temp", 24.0), ("hum", 48.0), ("gas", 300.0)):
        if name not in data:
            data[name] = baseline
            invented.append(name)
    simulated = [str(item) for item in (data.get("simulated") or [])]
    for name in invented:
        if name not in simulated:
            simulated.append(name)
    data["simulated"] = simulated
    data["temp"] = float(data["temp"])
    data["hum"] = float(data["hum"])
    data["gas"] = float(data["gas"])
    data["light"] = float(data["light"])
    return data


def parse_plain_status(text: str, device: str) -> dict:
    token = text.strip().lower()
    if token not in {"online", "offline"}:
        raise ValueError(f"Status is neither JSON nor online/offline: {text!r}")
    return {"device": device, "online": token == "online"}


def parse_ack(text: str, device: str) -> dict:
    raw = text.strip()
    lowered = raw.lower()
    if lowered.startswith("ok:"):
        command = raw[3:]
        return {
            "device": device,
            "type": "ack",
            "message": f"Commande acceptée : {command}",
            "severity": "info",
            "payload": {"ack": raw},
        }
    if lowered.startswith("erreur:"):
        command = raw[7:]
        return {
            "device": device,
            "type": "ack",
            "message": f"Commande refusée : {command}",
            "severity": "warning",
            "payload": {"ack": raw},
        }
    raise ValueError(f"Ack is neither ok: nor erreur:: {text!r}")


def device_command_text(auto: bool | None, scenario: str | None, target: str | None, state: str | None) -> str:
    """Plain command the ESP32 firmware accepts on .../cmd."""
    if auto:
        return "auto"
    if scenario:
        return f"scenario:{scenario}"
    bit = "1" if state == "on" else "0"
    return f"{target}:{bit}"
