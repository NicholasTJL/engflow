"""Sequential workflow executor: runs each step in dependency order."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from engflow.core.graph import topological_order
from engflow.core.models import WorkflowDefinition
from engflow.core.state import RunState, StepResult, StepStatus
from engflow.runners.base import StepRunner
from engflow.runners.command import CommandRunner
from engflow.runners.python import PythonRunner

RUNNERS: dict[str, StepRunner] = {
    "python": PythonRunner(),
    "command": CommandRunner(),
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_run_id() -> str:
    return f"{_now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"


def run_workflow(workflow: WorkflowDefinition, workflow_file: Path, run_dir: Path) -> RunState:
    """Execute every step of `workflow` in dependency order inside `run_dir`."""
    order = topological_order(workflow)
    steps_by_id = {step.id: step for step in workflow.steps}

    state = RunState(
        run_id=run_dir.name,
        workflow_name=workflow.name,
        workflow_file=str(workflow_file),
    )
    for step_id in order:
        state.steps[step_id] = StepResult(step_id=step_id)
    state.save(run_dir)

    failed_or_skipped: set[str] = set()

    for step_id in order:
        step = steps_by_id[step_id]
        result = state.steps[step_id]

        blocked_by = [dep for dep in step.depends_on if dep in failed_or_skipped]
        if blocked_by:
            result.status = StepStatus.SKIPPED
            result.error = f"skipped: dependency {blocked_by[0]!r} did not succeed"
            failed_or_skipped.add(step_id)
            state.save(run_dir)
            continue

        runner = RUNNERS.get(step.uses)
        if runner is None:
            result.status = StepStatus.FAILED
            result.error = f"no runner registered for uses={step.uses!r}"
            failed_or_skipped.add(step_id)
            state.save(run_dir)
            continue

        workdir = run_dir / "steps" / step_id
        workdir.mkdir(parents=True, exist_ok=True)
        result.workdir = str(workdir)
        result.stdout_path = str(workdir / "stdout.log")
        result.stderr_path = str(workdir / "stderr.log")
        result.status = StepStatus.RUNNING
        result.started_at = _now()
        state.save(run_dir)

        outcome = runner.run(step, workdir, workflow.parameters, run_dir)

        result.finished_at = _now()
        result.exit_code = outcome.exit_code
        if outcome.exit_code == 0:
            result.status = StepStatus.SUCCEEDED
        else:
            result.status = StepStatus.FAILED
            result.error = outcome.error
            failed_or_skipped.add(step_id)
        state.save(run_dir)

    state.status = StepStatus.FAILED if failed_or_skipped else StepStatus.SUCCEEDED
    state.finished_at = _now()
    state.save(run_dir)
    return state
