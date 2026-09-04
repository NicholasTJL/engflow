"""Run and step state: what actually happened when a workflow executed."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class StepResult(BaseModel):
    step_id: str
    status: StepStatus = StepStatus.PENDING
    started_at: datetime | None = None
    finished_at: datetime | None = None
    exit_code: int | None = None
    error: str | None = None
    workdir: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None


class RunState(BaseModel):
    run_id: str
    workflow_name: str
    workflow_file: str
    status: StepStatus = StepStatus.RUNNING
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    steps: dict[str, StepResult] = Field(default_factory=dict)

    def save(self, run_dir: Path) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run_state.json").write_text(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, run_dir: Path) -> RunState:
        state_file = run_dir / "run_state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"no run state found at {state_file}")
        return cls.model_validate_json(state_file.read_text())
