from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AlertCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "device": "esp01",
                    "type": "person",
                    "message": "Personne détectée devant la caméra",
                    "severity": "warning",
                }
            ]
        }
    )

    device: str = "esp01"
    type: str
    message: str
    severity: Literal["info", "warning", "critical"] = "warning"
    ts: int | None = None
    payload: dict = Field(default_factory=dict)


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device: str
    type: str
    message: str
    severity: str
    ts: int | None
    payload: dict
    source: str
    created_at: datetime
