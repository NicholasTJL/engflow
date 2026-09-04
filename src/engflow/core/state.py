"""Run and step state: what actually happened when a workflow executed."""

from __future__ import annotations

import os
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
    attempts: int = 0
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
        """Write `run_state.json` under `run_dir`.

        Writes to a temp file and renames it into place, so a reader (or a
        crash) never sees a partially written file. Callers that save this
        same `RunState` from multiple threads (as the concurrent executor
        does) must still serialize their calls with a lock -- this only
        protects against a torn *individual* write, not against two threads
        racing to write different snapshots of the state.
        """
        run_dir.mkdir(parents=True, exist_ok=True)
        final_path = run_dir / "run_state.json"
        tmp_path = run_dir / f".run_state.json.{os.getpid()}.tmp"
        # Written as bytes (not `write_text`), so the encoding is always
        # UTF-8 regardless of the platform's default text encoding --
        # `windows-latest` CI runners don't default to UTF-8 the way
        # Linux/macOS do.
        tmp_path.write_bytes(self.model_dump_json(indent=2).encode("utf-8"))
        os.replace(tmp_path, final_path)

    @classmethod
    def load(cls, run_dir: Path) -> RunState:
        state_file = run_dir / "run_state.json"
        if not state_file.exists():
            raise FileNotFoundError(f"no run state found at {state_file}")
        return cls.model_validate_json(state_file.read_bytes())
