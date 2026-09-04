"""Python-function step runner.

The target function is called as `function(context)`, where `context` is a
dict with `parameters` (the workflow's top-level parameters), `workdir`
(this step's working directory, as a string), and `run_dir` (the run's
shared root, so a step can read a prior step's workdir under
`run_dir/steps/<step_id>/` if it needs to).
"""

from __future__ import annotations

import contextlib
import importlib
import io
import sys
import traceback
from pathlib import Path

from engflow.core.models import StepDefinition
from engflow.runners.base import RunnerOutcome, StepRunner


class PythonRunner(StepRunner):
    def run(
        self,
        step: StepDefinition,
        workdir: Path,
        parameters: dict[str, object],
        run_dir: Path,
    ) -> RunnerOutcome:
        if not step.entrypoint:
            return RunnerOutcome(
                exit_code=1, error=f"step {step.id!r} uses 'python' but has no entrypoint set"
            )
        if ":" not in step.entrypoint:
            return RunnerOutcome(
                exit_code=1,
                error=(
                    f"step {step.id!r} entrypoint {step.entrypoint!r} must be "
                    "'module.path:function_name'"
                ),
            )

        module_name, _, function_name = step.entrypoint.partition(":")
        cwd = str(Path.cwd())
        if cwd not in sys.path:
            sys.path.insert(0, cwd)
        stdout_path = workdir / "stdout.log"
        stderr_path = workdir / "stderr.log"
        context = {"parameters": parameters, "workdir": str(workdir), "run_dir": str(run_dir)}

        try:
            module = importlib.import_module(module_name)
            function = getattr(module, function_name)
        except (ImportError, AttributeError) as exc:
            stderr_path.write_text(f"{exc}\n")
            return RunnerOutcome(
                exit_code=1, error=f"could not resolve entrypoint {step.entrypoint!r}: {exc}"
            )

        stdout_buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout_buffer):
                function(context)
        except Exception as exc:
            stdout_path.write_text(stdout_buffer.getvalue())
            stderr_path.write_text(traceback.format_exc())
            return RunnerOutcome(exit_code=1, error=f"{type(exc).__name__}: {exc}")

        stdout_path.write_text(stdout_buffer.getvalue())
        stderr_path.write_text("")
        return RunnerOutcome(exit_code=0)
