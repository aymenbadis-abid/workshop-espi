"""Slow scenario engine shared by the MQTT simulator.

Values follow the firmware contract: a base, a little noise, and a slow cycle.
`drift` is the case the server-side model must recognise later: temperature
climbs gradually while gas rises only slightly. `gas_leak` is a sharp spike.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

SCENARIOS = ("normal", "drift", "gas_leak", "reset")
SIMULATED_CHANNELS = ("temp", "hum", "gas")


@dataclass
class Sample:
    temp: float
    hum: float
    gas: float
    light: float
    simulated: list[str]


class ScenarioEngine:
    def __init__(self, rng: random.Random | None = None) -> None:
        self._rng = rng or random.Random()
        self.scenario = "normal"
        self.elapsed = 0.0

    def set_scenario(self, name: str) -> None:
        if name not in SCENARIOS:
            raise ValueError(f"Unknown scenario: {name}")
        if name == "reset":
            self.scenario = "normal"
            self.elapsed = 0.0
            return
        if name != self.scenario:
            self.elapsed = 0.0
        self.scenario = name

    def step(self, dt: float) -> Sample:
        self.elapsed += dt
        t = self.elapsed
        noise = self._rng.uniform(-0.3, 0.3)
        hum_noise = self._rng.uniform(-0.4, 0.4)
        gas_noise = self._rng.uniform(-4.0, 4.0)
        light_noise = self._rng.uniform(-8.0, 8.0)

        if self.scenario == "drift":
            temp = 24.0 + 0.02 * t + noise
            gas = 300.0 + 0.15 * t + gas_noise
            hum = 48.0 + 0.5 * math.sin(t / 40.0) + hum_noise
        elif self.scenario == "gas_leak":
            temp = 24.0 + 0.3 * math.sin(t / 30.0) + noise
            gas = 300.0 + 900.0 * (1.0 - math.exp(-t / 4.0)) + gas_noise
            hum = 48.0 + hum_noise
        else:
            temp = 24.0 + 0.4 * math.sin(t / 30.0) + noise
            gas = 300.0 + 8.0 * math.sin(t / 45.0) + gas_noise
            hum = 48.0 + 1.5 * math.sin(t / 50.0) + hum_noise

        light = 640.0 + 15.0 * math.sin(t / 20.0) + light_noise
        hum = min(100.0, max(0.0, hum))
        gas = max(0.0, gas)

        return Sample(
            temp=round(temp, 2),
            hum=round(hum, 2),
            gas=round(gas, 1),
            light=round(light, 1),
            simulated=list(SIMULATED_CHANNELS),
        )
