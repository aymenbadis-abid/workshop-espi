from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TelemetryIn(BaseModel):
    device: str
    ts: int
    temp: float
    hum: float
    gas: float
    light: float
    simulated: list[str] = Field(default_factory=list)
    gas_raw: float | None = None
    gas_delta: float | None = None
    gas_ready: int | None = None
    light_dark: int | None = None
    transitions_1min: int | None = None
    alert_heat: int | None = None
    alert_gas: int | None = None
    manual: int | None = None
    rssi: int | None = None


class TelemetryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device: str
    ts: int
    temp: float
    hum: float
    gas: float
    light: float
    simulated: list[str]
    gas_raw: float | None = None
    gas_delta: float | None = None
    gas_ready: int | None = None
    light_dark: int | None = None
    transitions_1min: int | None = None
    alert_heat: int | None = None
    alert_gas: int | None = None
    manual: int | None = None
    rssi: int | None = None
    received_at: datetime


class StatusIn(BaseModel):
    device: str
    online: bool
    ip: str | None = None
    uptime: int | None = None


class StatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    device: str
    online: bool
    ip: str | None = None
    uptime: int | None = None
    updated_at: datetime
