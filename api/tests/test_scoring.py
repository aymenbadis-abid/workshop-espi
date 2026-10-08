"""Simulated-channel filter and drift phrases. No database, no broker."""

import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "api"))
sys.path.insert(0, str(ROOT / "simulator"))

from app.modules.ml.decide import decide  # noqa: E402
from app.modules.ml.features import FEATURE_NAMES, WINDOW, feature_vector  # noqa: E402
from app.modules.ml.gate import MODEL_ABSENT, REAL_GAS_NO_ROOM, SIMULATED_GAS  # noqa: E402
from app.modules.ml.phrases import (  # noqa: E402
    SILENCE_LINE,
    TOGETHER,
    couple_phrase,
    rises_together,
    series_phrase,
)
from scenario import ScenarioEngine  # noqa: E402


class _Boom:
    def transform(self, _value):
        raise AssertionError("model was scored")

    def predict(self, _value):
        raise AssertionError("model was scored")


def _boom():
    return {
        "scaler": _Boom(),
        "model": _Boom(),
        "info": {
            "trained_on": "simulator",
            "channels": ["temp", "gas"],
            "name": "forêt d'isolation",
            "version": "simulator-couple",
        },
    }


class _Identity:
    def transform(self, value):
        return np.asarray(value, dtype=float)


class _AlwaysAnomaly:
    def predict(self, value):
        return np.array([-1])


def _always(trained_on: str, channels: list[str], version: str):
    return {
        "scaler": _Identity(),
        "model": _AlwaysAnomaly(),
        "info": {
            "trained_on": trained_on,
            "channels": channels,
            "name": "forêt d'isolation",
            "version": version,
            "algorithm": "isolation_forest",
        },
    }


def _row(index: int, temp: float, gas: float, simulated: list[str], step: int = 5) -> dict:
    return {
        "ts": 1_700_000_000 + index * step,
        "temp": temp,
        "hum": 48.0,
        "gas": gas,
        "simulated": simulated,
    }


def _drift_rows(simulated: list[str]) -> list[dict]:
    engine = ScenarioEngine(random.Random(3))
    engine.set_scenario("drift")
    engine.elapsed = 900.0
    rows = []
    for index in range(WINDOW):
        sample = engine.step(3.0)
        rows.append(_row(index, sample.temp, sample.gas, simulated, step=3))
        rows[-1]["hum"] = sample.hum
    return rows


def _features(rows: list[dict]) -> dict[str, float]:
    samples = [(row["temp"], row["gas"]) for row in rows]
    return dict(zip(FEATURE_NAMES, feature_vector(samples)))


def test_simulated_gas_with_real_temperature_is_not_scored() -> None:
    rows = [_row(index, 26.7, 300.0 + index, ["gas"]) for index in range(WINDOW)]
    result = decide(rows, simulator_bundle=_boom())
    assert result.pause == SIMULATED_GAS
    assert result.findings == ()
    assert not rises_together(_features(rows))


def test_real_gas_is_not_scored_with_the_simulator_model() -> None:
    rows = [_row(index, 26.7, 1800.0, []) for index in range(WINDOW)]
    result = decide(rows, simulator_bundle=_boom())
    assert result.pause == REAL_GAS_NO_ROOM
    assert result.findings == ()


def test_both_simulated_channels_may_be_scored() -> None:
    rows = _drift_rows(["temp", "hum", "gas"])
    result = decide(rows, simulator_bundle=_always("simulator", ["temp", "gas"], "simulator-couple-1"))
    assert result.pause is None
    assert len(result.findings) == 1
    assert result.findings[0].message == TOGETHER


def test_simulator_drift_rises_together() -> None:
    features = _features(_drift_rows(["temp", "hum", "gas"]))
    assert rises_together(features)
    assert couple_phrase(features) == TOGETHER
    assert "devriez" not in couple_phrase(features)


def test_one_rising_slope_is_not_called_together() -> None:
    rows = [_row(index, 24.0 + 0.08 * index, 300.0, ["temp", "hum", "gas"], step=3) for index in range(WINDOW)]
    features = _features(rows)
    phrase = couple_phrase(features)
    assert not rises_together(features)
    assert "montent ensemble" not in phrase
    assert "température" in phrase
    assert "pente" in phrase


def test_high_temperature_level_is_not_called_together() -> None:
    features = {
        "temp_slope": 0.0,
        "gas_slope": 0.0,
        "temp_mean": 32.0,
        "temp_std": 0.2,
        "gas_mean": 300.0,
        "gas_std": 2.0,
        "temp_gas_corr": 0.0,
    }
    zscores = {name: 0.1 for name in FEATURE_NAMES}
    zscores["temp_mean"] = 4.0
    phrase = couple_phrase(features, zscores)
    assert phrase == "Dérive détectée : température, niveau"
    assert "montent ensemble" not in phrase


def test_falling_gas_is_not_called_together() -> None:
    features = {
        "temp_slope": 0.08,
        "gas_slope": -0.3,
        "temp_mean": 26.0,
        "temp_std": 0.4,
        "gas_mean": 320.0,
        "gas_std": 4.0,
        "temp_gas_corr": 0.9,
    }
    assert not rises_together(features)
    assert "montent ensemble" not in couple_phrase(features)


def test_single_channel_phrase_never_says_together() -> None:
    phrase = series_phrase("hum", {"slope": 0.1, "mean": 2.0, "std": 0.2})
    assert phrase == "Dérive détectée : humidité, niveau"
    assert "montent ensemble" not in phrase


def test_room_couple_scores_only_when_both_channels_are_real() -> None:
    room = _always("room", ["temp", "gas"], "room-couple-1")
    real = [_row(index, 26.7, 1800.0, []) for index in range(WINDOW)]
    scored = decide(real, simulator_bundle=_boom(), room_couple_bundle=room)
    assert scored.pause is None
    assert len(scored.findings) == 1
    assert "montent ensemble" not in scored.findings[0].message
    mixed = [_row(index, 26.7, 300.0 + index, ["gas"]) for index in range(WINDOW)]
    paused = decide(mixed, simulator_bundle=_boom(), room_couple_bundle=room)
    assert paused.pause == SIMULATED_GAS
    assert paused.findings == ()


def test_real_temperature_can_be_named_alone_while_gas_is_simulated() -> None:
    series = _always("room", ["temp"], "room-temp-1")
    rows = [_row(index, 26.7, 300.0, ["gas"]) for index in range(WINDOW)]
    result = decide(rows, simulator_bundle=_boom(), room_temp_bundle=series)
    assert result.pause == SIMULATED_GAS
    assert len(result.findings) == 1
    assert result.findings[0].key == "temp"
    assert "montent ensemble" not in result.findings[0].message
    assert "température" in result.findings[0].message


def test_missing_simulator_model_is_inactive_not_a_drift() -> None:
    rows = _drift_rows(["temp", "hum", "gas"])
    result = decide(rows, simulator_bundle=None)
    assert result.pause is None
    assert result.findings == ()
    assert result.skipped == MODEL_ABSENT
    assert "détectée" not in result.skipped
    assert "devriez" not in result.skipped


def test_faster_feed_is_scored_on_a_five_second_grid() -> None:
    from app.modules.ml.gate import paced_rows

    rows = [_row(index, 26.0, 1800.0, [], step=2) for index in range(90)]
    paced = paced_rows(rows)
    assert len(paced) == WINDOW
    span = paced[-1]["ts"] - paced[0]["ts"]
    assert 100 <= span <= 200
    assert paced[-1]["ts"] - paced[-2]["ts"] >= 5


def test_silence_line_runs_for_two_minutes() -> None:
    from app.modules.ml.gate import should_emit, silence_line

    assert should_emit("phrase-test", "couple", now=1_000.0) is True
    assert silence_line("phrase-test", now=1_010.0) == SILENCE_LINE
    assert should_emit("phrase-test", "couple", now=1_010.0) is False
    assert silence_line("phrase-test", now=1_130.0) is None
    assert should_emit("phrase-test", "couple", now=1_130.0) is True


if __name__ == "__main__":
    test_simulated_gas_with_real_temperature_is_not_scored()
    test_real_gas_is_not_scored_with_the_simulator_model()
    test_both_simulated_channels_may_be_scored()
    test_simulator_drift_rises_together()
    test_one_rising_slope_is_not_called_together()
    test_high_temperature_level_is_not_called_together()
    test_falling_gas_is_not_called_together()
    test_single_channel_phrase_never_says_together()
    test_room_couple_scores_only_when_both_channels_are_real()
    test_real_temperature_can_be_named_alone_while_gas_is_simulated()
    test_missing_simulator_model_is_inactive_not_a_drift()
    test_faster_feed_is_scored_on_a_five_second_grid()
    test_silence_line_runs_for_two_minutes()
    print("scoring checks ok")
