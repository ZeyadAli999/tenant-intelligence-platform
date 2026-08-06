"""Shared Pydantic schema configuration."""

from pydantic import BaseModel, ConfigDict


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
