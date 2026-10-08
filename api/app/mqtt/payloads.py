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


_BOARD_FLOATS = ("gas_raw", "gas_delta")
_BOARD_INTS = (
    "gas_ready",
    "light_dark",
    "transitions_1min",
    "alert_heat",
    "alert_gas",
    "manual",
    "rssi",
)


def _number_or_none(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().lower() in {"", "null", "nan"}:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _optional_float(data: dict, key: str) -> float | None:
    if key not in data or data[key] is None:
        return None
    return _number_or_none(data[key])


def _optional_int(data: dict, key: str) -> int | None:
    number = _optional_float(data, key)
    if number is None:
        return None
    return int(number)


def normalize_telemetry(raw: dict, device_hint: str | None = None) -> dict:
    """Fill the fields the dashboard stores when the board omits them.

    A payload that already matches the simulator contract is returned unchanged
    apart from numeric coercion. The DHT22 sketch names the same readings
    temperature and humidity. light_dark without light becomes a chart value.
    A missing or null channel gets a neutral baseline and is marked simulated.

    Board facts (gas warmup, heat and gas flags, light, manual, rssi) are kept
    when the board sent them. A missing key stays null: it is not a warmup and
    not a heat level.
    """
    data = dict(raw)
    if device_hint and not data.get("device"):
        data["device"] = device_hint
    if "ts" not in data:
        data["ts"] = int(time.time())
    else:
        data["ts"] = int(data["ts"])

    if "temp" not in data:
        parsed = _number_or_none(data.get("temperature"))
        if parsed is not None:
            data["temp"] = parsed
    if "hum" not in data:
        parsed = _number_or_none(data.get("humidity"))
        if parsed is not None:
            data["hum"] = parsed

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
    for key in _BOARD_FLOATS:
        data[key] = _optional_float(raw, key)
    for key in _BOARD_INTS:
        data[key] = _optional_int(raw, key)
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
