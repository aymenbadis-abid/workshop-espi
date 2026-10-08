"""Scoring status returned to the screen. Findings themselves stay on alerts."""

from pydantic import BaseModel


class ModelCardOut(BaseModel):
    loaded: bool
    role: str
    name: str | None = None
    version: str | None = None
    trained_on: str | None = None
    channels: list[str] | None = None


class DeviceScoringOut(BaseModel):
    device: str
    joint_drift: str | None = None
    silence: str | None = None
    models: dict[str, ModelCardOut]


class ScoringOut(BaseModel):
    devices: list[DeviceScoringOut]
