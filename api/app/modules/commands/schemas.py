from typing import Literal

from pydantic import BaseModel, model_validator


class CommandIn(BaseModel):
    target: Literal["led_red", "led_green", "buzzer"] | None = None
    state: Literal["on", "off"] | None = None
    scenario: Literal["normal", "drift", "gas_leak", "reset"] | None = None
    auto: bool | None = None

    @model_validator(mode="after")
    def exactly_one_command(self) -> "CommandIn":
        if self.auto is False:
            raise ValueError("Send auto as true, or omit it.")
        has_scenario = self.scenario is not None
        has_auto = self.auto is True
        has_output = self.target is not None or self.state is not None
        if sum((has_scenario, has_auto, has_output)) != 1:
            raise ValueError("Send a LED or buzzer command, a scenario, or auto.")
        if has_output and (self.target is None or self.state is None):
            raise ValueError("A LED or buzzer command needs both target and state.")
        return self


class CommandOut(BaseModel):
    published: bool
    topic: str
