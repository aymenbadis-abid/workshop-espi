"""JWT will be attached before the demo. This module holds the future boundary."""

from pydantic import BaseModel


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
