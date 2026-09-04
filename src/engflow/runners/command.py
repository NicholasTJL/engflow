"""Command-line step runner."""

from __future__ import annotations

import subprocess
from pathlib import Path

from engflow.core.models import StepDefinition
from engflow.runners.base import RunnerOutcome, StepRunner


class CommandRunner(StepRunner):
    def run(
        self,
        step: StepDefinition,
        workdir: Path,
        parameters: dict[str, object],
        run_dir: Path,
    ) -> RunnerOutcome:
        del parameters, run_dir
        if not step.command:
            return RunnerOutcome(
                exit_code=1, error=f"step {step.id!r} uses 'command' but has no command set"
            )

        stdout_path = workdir / "stdout.log"
        stderr_path = workdir / "stderr.log"

        try:
            with stdout_path.open("w") as stdout_file, stderr_path.open("w") as stderr_file:
                completed = subprocess.run(
                    step.command,
                    shell=True,
                    cwd=workdir,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=step.timeout,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            return RunnerOutcome(
                exit_code=1, error=f"step {step.id!r} timed out after {step.timeout}s"
            )

        if completed.returncode != 0:
            return RunnerOutcome(
                exit_code=completed.returncode,
                error=f"command exited with status {completed.returncode}; see stderr.log",
            )
        return RunnerOutcome(exit_code=0)
