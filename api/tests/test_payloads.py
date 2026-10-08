"""Checks for the ESP32 topic and payload adapter. No database, no broker."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mqtt.payloads import (  # noqa: E402
    classify_topic,
    device_command_text,
    normalize_telemetry,
    parse_ack,
    parse_plain_status,
)

SIM = "sentinelx/g6"
BOARD = "sentinelx/esp32-01"


def test_classify_keeps_simulator_and_board_apart() -> None:
    assert classify_topic(f"{BOARD}/telemetry", SIM, BOARD) == ("telemetry", "esp32-01")
    assert classify_topic(f"{BOARD}/ack", SIM, BOARD) == ("ack", "esp32-01")
    assert classify_topic(f"{SIM}/cmd", SIM, BOARD) is None
    assert classify_topic(f"{SIM}/telemetry", SIM, BOARD) == ("telemetry", None)
    assert classify_topic("other/telemetry", SIM, BOARD) is None


def test_original_board_telemetry_becomes_storable() -> None:
    raw = {
        "device": "esp32-01",
        "uptime_s": 12,
        "light_dark": 1,
        "transitions_1min": 2,
        "status": "ALERTE",
        "manual": 0,
        "rssi": -40,
    }
    out = normalize_telemetry(raw, "esp32-01")
    assert out["device"] == "esp32-01"
    assert out["light"] == 80.0
    assert out["temp"] == 24.0
    assert out["simulated"] == ["temp", "hum", "gas"]
    assert "ts" in out
    assert out["gas_ready"] is None
    assert out["gas_raw"] is None
    assert out["alert_heat"] is None
    assert out["light_dark"] == 1
    assert out["manual"] == 0
    assert out["rssi"] == -40


def test_dht_telemetry_keeps_real_temperature_and_humidity() -> None:
    raw = {
        "device": "esp32-01",
        "uptime_s": 255,
        "temperature": 26.7,
        "humidity": 48.9,
        "light_dark": 0,
        "transitions_1min": 0,
        "alert_heat": 0,
        "status": "NORMAL",
        "manual": 0,
        "rssi": -50,
    }
    out = normalize_telemetry(raw, "esp32-01")
    assert out["temp"] == 26.7
    assert out["hum"] == 48.9
    assert out["light"] == 640.0
    assert out["gas"] == 300.0
    assert out["simulated"] == ["gas"]
    assert out["gas_ready"] is None
    assert out["gas_raw"] is None
    assert out["alert_heat"] == 0
    assert out["light_dark"] == 0
    assert out["rssi"] == -50


def test_missing_dht_reading_is_marked_simulated() -> None:
    raw = {
        "device": "esp32-01",
        "temperature": None,
        "humidity": None,
        "light_dark": 1,
    }
    out = normalize_telemetry(raw, "esp32-01")
    assert out["light"] == 80.0
    assert out["simulated"] == ["temp", "hum", "gas"]


def test_full_contract_is_not_rewritten() -> None:
    raw = {
        "device": "esp32-01",
        "ts": 1760000000,
        "temp": 24.5,
        "hum": 48,
        "gas": 312,
        "light": 640,
        "simulated": ["temp", "hum", "gas"],
    }
    out = normalize_telemetry(raw, "esp32-01")
    assert out["ts"] == 1760000000
    assert out["light"] == 640.0
    assert out["simulated"] == ["temp", "hum", "gas"]


def test_board_facts_are_kept() -> None:
    raw = {
        "device": "esp32-01",
        "ts": 1760000000,
        "temp": 26.5,
        "hum": 48.0,
        "gas": 1810.0,
        "light": 640,
        "simulated": [],
        "gas_raw": 1820,
        "gas_delta": 0,
        "gas_ready": 1,
        "light_dark": 0,
        "transitions_1min": 3,
        "alert_heat": 1,
        "alert_gas": 0,
        "manual": 1,
        "rssi": -48,
    }
    out = normalize_telemetry(raw, "esp32-01")
    assert out["simulated"] == []
    assert out["gas"] == 1810.0
    assert out["gas_raw"] == 1820.0
    assert out["gas_delta"] == 0.0
    assert out["gas_ready"] == 1
    assert out["alert_heat"] == 1
    assert out["alert_gas"] == 0
    assert out["manual"] == 1
    assert out["rssi"] == -48


def test_warmup_keeps_the_raw_reading_and_the_simulated_chart_value() -> None:
    raw = {
        "device": "esp32-01",
        "ts": 1760000000,
        "temp": 26.5,
        "hum": 48.0,
        "gas": 300.0,
        "light": 640,
        "simulated": ["gas"],
        "gas_raw": 1500,
        "gas_delta": None,
        "gas_ready": 0,
        "alert_gas": 0,
        "alert_heat": 0,
    }
    out = normalize_telemetry(raw, "esp32-01")
    assert out["simulated"] == ["gas"]
    assert out["gas"] == 300.0
    assert out["gas_raw"] == 1500.0
    assert out["gas_delta"] is None
    assert out["gas_ready"] == 0


def test_status_and_ack_text() -> None:
    assert parse_plain_status("offline", "esp32-01")["online"] is False
    ok = parse_ack("ok:led_red:1", "esp32-01")
    assert ok["severity"] == "info"
    assert "led_red:1" in ok["message"]
    bad = parse_ack("erreur:nope", "esp32-01")
    assert bad["severity"] == "warning"


def test_command_text_matches_the_board() -> None:
    assert device_command_text(True, None, None, None) == "auto"
    assert device_command_text(None, "drift", None, None) == "scenario:drift"
    assert device_command_text(None, None, "led_red", "on") == "led_red:1"
    assert device_command_text(None, None, "buzzer", "off") == "buzzer:0"


if __name__ == "__main__":
    test_classify_keeps_simulator_and_board_apart()
    test_original_board_telemetry_becomes_storable()
    test_dht_telemetry_keeps_real_temperature_and_humidity()
    test_missing_dht_reading_is_marked_simulated()
    test_full_contract_is_not_rewritten()
    test_board_facts_are_kept()
    test_warmup_keeps_the_raw_reading_and_the_simulated_chart_value()
    test_status_and_ack_text()
    test_command_text_matches_the_board()
    print("payload checks ok")
