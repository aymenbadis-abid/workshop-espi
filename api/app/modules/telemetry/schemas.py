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
