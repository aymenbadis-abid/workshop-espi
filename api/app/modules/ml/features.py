"""Sliding-window features for the anomaly model.

The vector describes the shape of temperature and gas together: slopes, level,
spread, and how the two series move with each other. It does not compare a
reading to a fixed limit.
"""

from __future__ import annotations

import numpy as np

WINDOW = 30
FEATURE_NAMES = (
    "temp_slope",
    "gas_slope",
    "temp_mean",
    "temp_std",
    "gas_mean",
    "gas_std",
    "temp_gas_corr",
)
SERIES_FEATURE_NAMES = ("slope", "mean", "std")


def _slope(index: np.ndarray, values: np.ndarray) -> float:
    centered = index - index.mean()
    variance = float((centered ** 2).sum())
    if variance < 1e-9:
        return 0.0
    return float((centered * (values - values.mean())).sum() / variance)


def _correlation(left: np.ndarray, right: np.ndarray) -> float:
    if float(left.std()) < 1e-9 or float(right.std()) < 1e-9:
        return 0.0
    return float(np.corrcoef(left, right)[0, 1])


def feature_vector(samples: list[tuple[float, float]]) -> np.ndarray:
    """Build one feature row from (temperature, gas) pairs, oldest first."""
    if len(samples) != WINDOW:
        raise ValueError(f"Expected {WINDOW} samples, got {len(samples)}")
    temps = np.array([sample[0] for sample in samples], dtype=float)
    gases = np.array([sample[1] for sample in samples], dtype=float)
    index = np.arange(WINDOW, dtype=float)
    return np.array(
        [
            _slope(index, temps),
            _slope(index, gases),
            float(temps.mean()),
            float(temps.std()),
            float(gases.mean()),
            float(gases.std()),
            _correlation(temps, gases),
        ],
        dtype=float,
    )


def series_feature_vector(values: list[float]) -> np.ndarray:
    """Build one feature row from a single channel, oldest first.

    Temperature and humidity each have their own vector. Gas and light are not
    described here.
    """
    if len(values) != WINDOW:
        raise ValueError(f"Expected {WINDOW} samples, got {len(values)}")
    series = np.array(values, dtype=float)
    index = np.arange(WINDOW, dtype=float)
    return np.array(
        [_slope(index, series), float(series.mean()), float(series.std())],
        dtype=float,
    )
