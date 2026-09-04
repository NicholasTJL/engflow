"""Runner protocol: how a single step actually executes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from engflow.core.models import StepDefinition


@dataclass
class RunnerOutcome:
    exit_code: int
    error: str | None = None


class StepRunner(ABC):
    """One runner implementation per `StepDefinition.uses` value."""

    @abstractmethod
    def run(
        self,
        step: StepDefinition,
        workdir: Path,
        parameters: dict[str, object],
        run_dir: Path,
    ) -> RunnerOutcome:
        """Execute `step` inside `workdir`, writing stdout.log/stderr.log there.

        `run_dir` is the shared root for this whole run (containing every
        step's workdir under `run_dir/steps/<step_id>/`), so a step can read
        artifacts a prior step wrote, if it needs to.
        """
