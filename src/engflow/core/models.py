"""Pydantic schema for engflow workflow definitions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class StepDefinition(BaseModel):
    """A single unit of work in a workflow."""

    id: str
    uses: Literal["python", "command", "template"]
    entrypoint: str | None = None
    command: str | None = None
    template: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    timeout: int | None = None
    retries: int = 0

    @field_validator("id")
    @classmethod
    def id_must_be_identifier(cls, value: str) -> str:
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError(f"step id {value!r} must be alphanumeric (with - or _)")
        return value


class WorkflowDefinition(BaseModel):
    """A full workflow: a name, optional parameters, and an ordered list of steps."""

    name: str
    parameters: dict[str, object] = Field(default_factory=dict)
    steps: list[StepDefinition]

    @field_validator("steps")
    @classmethod
    def steps_must_be_unique(cls, steps: list[StepDefinition]) -> list[StepDefinition]:
        ids = [step.id for step in steps]
        duplicates = sorted({step_id for step_id in ids if ids.count(step_id) > 1})
        if duplicates:
            raise ValueError(f"duplicate step ids: {duplicates}")
        return steps
