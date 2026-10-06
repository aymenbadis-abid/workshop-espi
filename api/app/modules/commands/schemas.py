from typing import Literal

from pydantic import BaseModel, model_validator


class CommandIn(BaseModel):
    target: Literal["led_red", "led_green"] | None = None
    state: Literal["on", "off"] | None = None
    scenario: Literal["normal", "drift", "gas_leak", "reset"] | None = None

    @model_validator(mode="after")
    def exactly_one_command(self) -> "CommandIn":
        led = self.target is not None or self.state is not None
        scenario = self.scenario is not None
        if scenario and self.target is None and self.state is None:
            return self
        if self.target is not None and self.state is not None and not scenario:
            return self
        raise ValueError("Send either a LED target and state, or a scenario.")


class CommandOut(BaseModel):
    published: bool
    topic: str
