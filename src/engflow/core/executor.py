"""Workflow executor: runs steps concurrently, respecting dependencies.

Steps are scheduled as soon as every step they `depends_on` has succeeded,
up to `max_concurrency` running at once -- not strictly one-at-a-time in
topological order. A step whose dependency failed or was skipped is itself
marked skipped, exactly as in the old sequential executor. Each step that
fails is retried (with exponential backoff) up to `step.retries` times
before being marked failed for good.

`RunState.save()` writes the whole run's state to one JSON file, and
multiple step threads finish at unpredictable times, so every read-modify-
write of `state` (updating a step's status, then saving) is done while
holding `_state_lock`. That serializes the file writes and prevents two
threads from interleaving a save and corrupting `run_state.json`; it isn't
meant to be a high-throughput lock, just a correct one.
"""

from __future__ import annotations

import copy
import time
import uuid
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from engflow.core.graph import topological_order
from engflow.core.models import StepDefinition, WorkflowDefinition
from engflow.core.state import RunState, StepResult, StepStatus
from engflow.runners.base import StepRunner
from engflow.runners.command import CommandRunner
from engflow.runners.python import PythonRunner

RUNNERS: dict[str, StepRunner] = {
    "python": PythonRunner(),
    "command": CommandRunner(),
}

DEFAULT_MAX_CONCURRENCY = 4


def _now() -> datetime:
    return datetime.now(timezone.utc)


def new_run_id() -> str:
    return f"{_now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"


def _run_step_with_retries(
    step: StepDefinition, workdir: Path, parameters: dict[str, object], run_dir: Path
) -> tuple[int, str | None, int]:
    """Run `step`, retrying on failure up to `step.retries` extra times.

    Backoff between attempts is exponential starting at 1 second (1, 2, 4,
    ...). Returns (exit_code, error, attempts_made) from the final attempt.
    """
    runner = RUNNERS.get(step.uses)
    if runner is None:
        return 1, f"no runner registered for uses={step.uses!r}", 1

    max_attempts = step.retries + 1
    attempt = 0
    while True:
        attempt += 1
        outcome = runner.run(step, workdir, parameters, run_dir)
        if outcome.exit_code == 0 or attempt >= max_attempts:
            return outcome.exit_code, outcome.error, attempt
        time.sleep(2 ** (attempt - 1))


def run_workflow(
    workflow: WorkflowDefinition,
    workflow_file: Path,
    run_dir: Path,
    *,
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
    resume_state: RunState | None = None,
) -> RunState:
    """Execute every step of `workflow`, respecting dependencies, inside `run_dir`.

    Steps with no unmet dependencies run concurrently, up to
    `max_concurrency` at once. If `resume_state` is given (typically loaded
    from a prior, interrupted run in this same `run_dir`), any step that
    already succeeded there is copied over as-is and not re-run; everything
    else runs normally.
    """
    max_concurrency = max(1, max_concurrency)
    order = topological_order(workflow)
    steps_by_id = {step.id: step for step in workflow.steps}

    state = RunState(
        run_id=run_dir.name,
        workflow_name=workflow.name,
        workflow_file=str(workflow_file),
    )
    for step_id in order:
        state.steps[step_id] = StepResult(step_id=step_id)

    # `resolved` records the final status of every step already decided,
    # either because a prior run resumed here already succeeded, or because
    # it finished (or was skipped) during this run.
    resolved: dict[str, StepStatus] = {}
    if resume_state is not None:
        for step_id in order:
            prior = resume_state.steps.get(step_id)
            if prior is not None and prior.status == StepStatus.SUCCEEDED:
                state.steps[step_id] = prior.model_copy()
                resolved[step_id] = StepStatus.SUCCEEDED

    lock = Lock()
    with lock:
        state.save(run_dir)

    remaining = [step_id for step_id in order if step_id not in resolved]

    def execute(step_id: str) -> None:
        step = steps_by_id[step_id]
        result = state.steps[step_id]

        workdir = run_dir / "steps" / step_id
        workdir.mkdir(parents=True, exist_ok=True)
        with lock:
            result.workdir = str(workdir)
            result.stdout_path = str(workdir / "stdout.log")
            result.stderr_path = str(workdir / "stderr.log")
            result.status = StepStatus.RUNNING
            result.started_at = _now()
            state.save(run_dir)

        # Each step gets its own deep copy of the workflow parameters: several
        # steps can be running in different threads at once, and a python
        # step that mutates `context["parameters"]` (e.g. `params["x"] = y`,
        # or appending to a list value) must not leak that mutation into a
        # concurrently running sibling step.
        step_parameters = copy.deepcopy(workflow.parameters)
        exit_code, error, attempts = _run_step_with_retries(
            step, workdir, step_parameters, run_dir
        )

        with lock:
            result.finished_at = _now()
            result.exit_code = exit_code
            result.attempts = attempts
            result.status = StepStatus.SUCCEEDED if exit_code == 0 else StepStatus.FAILED
            result.error = error
            state.save(run_dir)

    with ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        in_flight: dict[Future[None], str] = {}

        while remaining or in_flight:
            # Steps blocked by an already-failed/skipped dependency resolve
            # instantly -- no need to wait for a pool slot for those.
            progressed = True
            while progressed:
                progressed = False
                for step_id in list(remaining):
                    step = steps_by_id[step_id]
                    dep_statuses = [resolved.get(dep) for dep in step.depends_on]
                    if any(status is None for status in dep_statuses):
                        continue
                    blocked_by = [
                        dep
                        for dep, status in zip(step.depends_on, dep_statuses, strict=True)
                        if status != StepStatus.SUCCEEDED
                    ]
                    if not blocked_by:
                        continue
                    remaining.remove(step_id)
                    result = state.steps[step_id]
                    with lock:
                        result.status = StepStatus.SKIPPED
                        result.error = f"skipped: dependency {blocked_by[0]!r} did not succeed"
                        state.save(run_dir)
                    resolved[step_id] = StepStatus.SKIPPED
                    progressed = True

            # Submit every step whose dependencies have all succeeded, up to
            # however many pool slots are free. The instant-skip pass above
            # already removed any step with a failed/skipped dependency, so
            # a step still `remaining` here either has an unresolved
            # dependency (skip it, not ready yet) or has every dependency
            # succeeded (submit it).
            for step_id in list(remaining):
                if len(in_flight) >= max_concurrency:
                    break
                step = steps_by_id[step_id]
                if any(resolved.get(dep) is None for dep in step.depends_on):
                    continue
                remaining.remove(step_id)
                future = pool.submit(execute, step_id)
                in_flight[future] = step_id

            if not in_flight:
                if remaining:
                    # topological_order() already rejects cycles, so every
                    # remaining step's dependencies should eventually
                    # resolve. This is only reachable if that invariant is
                    # broken.
                    raise RuntimeError(f"scheduling deadlock; unresolved steps: {remaining}")
                break  # everything resolved (the last steps all skipped instantly)

            done, _ = wait(in_flight.keys(), return_when=FIRST_COMPLETED)
            for future in done:
                step_id = in_flight.pop(future)
                future.result()  # re-raise if `execute` raised unexpectedly
                resolved[step_id] = state.steps[step_id].status

    with lock:
        state.status = (
            StepStatus.FAILED
            if any(status != StepStatus.SUCCEEDED for status in resolved.values())
            else StepStatus.SUCCEEDED
        )
        state.finished_at = _now()
        state.save(run_dir)
    return state
