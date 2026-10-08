"""French sentences for sensor findings.

These sentences name a shape that was already calculated. They do not advise
an action. A local language model is not called: the fixed sentence is the
one stored on the alert.
"""

from __future__ import annotations

TOGETHER = "Dérive détectée : température et gaz montent ensemble"
SILENCE_LINE = "Silence de 2 minutes en cours."

# Slopes are per sample in the window, not per second. A late simulator drift
# climbs about 0.06 °C and about 0.37 gas units per sample.
TEMP_SLOPE_MIN = 0.02
GAS_SLOPE_MIN = 0.08
CORR_MIN = 0.7

_COUPLE_SHAPE = {
    "temp_slope": ("température", "pente"),
    "temp_mean": ("température", "niveau"),
    "temp_std": ("température", "écart"),
    "gas_slope": ("gaz", "pente"),
    "gas_mean": ("gaz", "niveau"),
    "gas_std": ("gaz", "écart"),
}
_SERIES_SHAPE = {"slope": "pente", "mean": "niveau", "std": "écart"}
_SERIES_LABEL = {"temp": "température", "hum": "humidité"}
_FORBIDDEN = ("devriez", "aérer", "aérez", "éteindre", "éteignez", "appeler", "appelez", "conseil")


def _observation(text: str) -> str:
    lowered = text.lower()
    for word in _FORBIDDEN:
        if word in lowered:
            raise ValueError(f"Sentence advises an action: {text}")
    return text


def rises_together(features: dict[str, float]) -> bool:
    """True only when both slopes climb and the two series move together."""
    return (
        features["temp_slope"] > TEMP_SLOPE_MIN
        and features["gas_slope"] > GAS_SLOPE_MIN
        and features["temp_gas_corr"] >= CORR_MIN
    )


def _dominant_couple(features: dict[str, float], zscores: dict[str, float] | None) -> tuple[str, str]:
    if zscores:
        names = [name for name in _COUPLE_SHAPE if name in zscores]
        if names:
            chosen = max(names, key=lambda name: abs(zscores[name]))
            return _COUPLE_SHAPE[chosen]
    if abs(features["temp_slope"]) >= abs(features["gas_slope"]) and abs(features["temp_slope"]) > TEMP_SLOPE_MIN:
        return "température", "pente"
    if abs(features["gas_slope"]) > GAS_SLOPE_MIN:
        return "gaz", "pente"
    if features["temp_std"] >= features["gas_std"] and features["temp_std"] > 0.5:
        return "température", "écart"
    if features["gas_std"] > 8.0:
        return "gaz", "écart"
    return "température", "niveau"


def couple_phrase(features: dict[str, float], zscores: dict[str, float] | None = None) -> str:
    """Name a joint finding. 'montent ensemble' is reserved for two rising slopes."""
    if rises_together(features):
        return _observation(TOGETHER)
    channel, shape = _dominant_couple(features, zscores)
    return _observation(f"Dérive détectée : {channel}, {shape}")


def couple_detail(features: dict[str, float]) -> str:
    return _observation(
        f"Température moyenne {features['temp_mean']:.1f} °C, pente {features['temp_slope']:+.3f}. "
        f"Moyenne du gaz {features['gas_mean']:.0f}, pente {features['gas_slope']:+.3f}. "
        f"Lien {features['temp_gas_corr']:+.2f}."
    )


def series_phrase(channel: str, zscores: dict[str, float]) -> str:
    """Name one channel. Never claims that temperature and gas rise together."""
    if channel not in _SERIES_LABEL:
        raise ValueError(f"No single-channel phrase for {channel}")
    shape_key = max(_SERIES_SHAPE, key=lambda name: abs(zscores.get(name, 0.0)))
    text = f"Dérive détectée : {_SERIES_LABEL[channel]}, {_SERIES_SHAPE[shape_key]}"
    if "montent ensemble" in text:
        raise ValueError(text)
    return _observation(text)


def series_detail(channel: str, stats: dict[str, float]) -> str:
    if channel == "temp":
        text = (
            f"Température moyenne {stats['mean']:.1f} °C, "
            f"pente {stats['slope']:+.3f}, écart {stats['std']:.2f}."
        )
    elif channel == "hum":
        text = (
            f"Humidité moyenne {stats['mean']:.1f} %, "
            f"pente {stats['slope']:+.3f}, écart {stats['std']:.2f}."
        )
    else:
        raise ValueError(f"No single-channel detail for {channel}")
    return _observation(text)
