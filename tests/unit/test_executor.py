import json
from pathlib import Path

import pytest

from engflow.core.executor import run_workflow
from engflow.core.models import StepDefinition, WorkflowDefinition
from engflow.core.state import RunState, StepStatus


def _workflow(
    steps: list[StepDefinition], parameters: dict[str, object] | None = None
) -> WorkflowDefinition:
    return WorkflowDefinition(name="test", parameters=parameters or {}, steps=steps)


def _read_timing(run_dir: Path, step_id: str) -> tuple[float, float]:
    text = (run_dir / "steps" / step_id / "timing.txt").read_text()
    start, end = (float(value) for value in text.split())
    return start, end


def test_sequential_command_steps_succeed(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(id="write", uses="command", command="echo hello"),
            StepDefinition(
                id="read", uses="command", command="echo world", depends_on=["write"]
            ),
        ]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.SUCCEEDED
    assert state.steps["write"].status == StepStatus.SUCCEEDED
    assert state.steps["read"].status == StepStatus.SUCCEEDED
    assert (tmp_path / "run" / "run_state.json").exists()


def test_failed_step_skips_dependents(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(id="a", uses="command", command="exit 1"),
            StepDefinition(id="b", uses="command", command="echo hi", depends_on=["a"]),
        ]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.FAILED
    assert state.steps["a"].status == StepStatus.FAILED
    assert state.steps["b"].status == StepStatus.SKIPPED
    assert "did not succeed" in (state.steps["b"].error or "")


def test_unrunnable_uses_fails_cleanly(tmp_path: Path) -> None:
    workflow = _workflow(
        [StepDefinition(id="a", uses="template", template="templates/report.html")]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.FAILED
    assert state.steps["a"].status == StepStatus.FAILED
    assert "no runner registered" in (state.steps["a"].error or "")


def test_python_step_succeeds(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(
                id="greet",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:write_greeting",
            )
        ],
        parameters={"name": "engflow"},
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.SUCCEEDED
    greeting = tmp_path / "run" / "steps" / "greet" / "greeting.txt"
    assert greeting.read_text() == "hello, engflow\n"


def test_python_step_failure_is_captured(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(
                id="boom",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:always_fails",
            )
        ]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.FAILED
    assert "this step always fails" in (state.steps["boom"].error or "")
    stderr_path = tmp_path / "run" / "steps" / "boom" / "stderr.log"
    assert "RuntimeError" in stderr_path.read_text()


def test_run_state_round_trips(tmp_path: Path) -> None:
    workflow = _workflow([StepDefinition(id="a", uses="command", command="echo hi")])
    run_dir = tmp_path / "run"

    run_workflow(workflow, tmp_path / "workflow.yaml", run_dir)
    loaded = RunState.load(run_dir)

    assert loaded.workflow_name == "test"
    assert loaded.steps["a"].status == StepStatus.SUCCEEDED


def test_succeeded_step_records_a_single_attempt(tmp_path: Path) -> None:
    workflow = _workflow([StepDefinition(id="a", uses="command", command="echo hi")])

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.steps["a"].attempts == 1


# --- Retries -----------------------------------------------------------------


def test_retries_recover_from_a_step_that_eventually_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("engflow.core.executor.time.sleep", lambda _seconds: None)
    workflow = _workflow(
        [
            StepDefinition(
                id="flaky",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:fail_twice_then_succeed",
                retries=2,
            )
        ]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.SUCCEEDED
    assert state.steps["flaky"].status == StepStatus.SUCCEEDED
    assert state.steps["flaky"].attempts == 3


def test_retries_exhausted_marks_step_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("engflow.core.executor.time.sleep", lambda _seconds: None)
    workflow = _workflow(
        [
            StepDefinition(
                id="boom",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:always_fails",
                retries=2,
            )
        ]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.status == StepStatus.FAILED
    assert state.steps["boom"].status == StepStatus.FAILED
    assert state.steps["boom"].attempts == 3
    assert "this step always fails" in (state.steps["boom"].error or "")


def test_retry_backoff_is_exponential(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("engflow.core.executor.time.sleep", sleeps.append)
    workflow = _workflow(
        [
            StepDefinition(
                id="boom",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:always_fails",
                retries=3,
            )
        ]
    )

    run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert sleeps == [1, 2, 4]


def test_zero_retries_fails_after_one_attempt(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(
                id="boom", uses="python", entrypoint="tests.fixtures.sample_steps:always_fails"
            )
        ]
    )

    state = run_workflow(workflow, tmp_path / "workflow.yaml", tmp_path / "run")

    assert state.steps["boom"].attempts == 1


# --- Concurrency ---------------------------------------------------------------


def test_independent_steps_run_concurrently(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(
                id="x", uses="python", entrypoint="tests.fixtures.sample_steps:record_start_and_end"
            ),
            StepDefinition(
                id="y", uses="python", entrypoint="tests.fixtures.sample_steps:record_start_and_end"
            ),
        ]
    )
    run_dir = tmp_path / "run"

    state = run_workflow(workflow, tmp_path / "workflow.yaml", run_dir, max_concurrency=2)

    assert state.status == StepStatus.SUCCEEDED
    x_start, x_end = _read_timing(run_dir, "x")
    y_start, y_end = _read_timing(run_dir, "y")
    assert x_start < y_end and y_start < x_end, "independent steps did not overlap in time"


def test_max_concurrency_one_serializes_independent_steps(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(
                id="x", uses="python", entrypoint="tests.fixtures.sample_steps:record_start_and_end"
            ),
            StepDefinition(
                id="y", uses="python", entrypoint="tests.fixtures.sample_steps:record_start_and_end"
            ),
        ]
    )
    run_dir = tmp_path / "run"

    state = run_workflow(workflow, tmp_path / "workflow.yaml", run_dir, max_concurrency=1)

    assert state.status == StepStatus.SUCCEEDED
    x_start, x_end = _read_timing(run_dir, "x")
    y_start, y_end = _read_timing(run_dir, "y")
    assert x_end <= y_start or y_end <= x_start, "steps overlapped despite --max-concurrency 1"


def test_concurrent_steps_do_not_share_a_mutable_parameters_object(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(
                id="m1",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:mutate_parameters_and_record",
            ),
            StepDefinition(
                id="m2",
                uses="python",
                entrypoint="tests.fixtures.sample_steps:mutate_parameters_and_record",
            ),
        ],
        parameters={"shared": "value"},
    )
    run_dir = tmp_path / "run"

    state = run_workflow(workflow, tmp_path / "workflow.yaml", run_dir, max_concurrency=2)

    assert state.status == StepStatus.SUCCEEDED
    m1_params = json.loads((run_dir / "steps" / "m1" / "params.json").read_text())
    m2_params = json.loads((run_dir / "steps" / "m2" / "params.json").read_text())
    assert m1_params == {"shared": "value", "seen_by_m1": True}
    assert m2_params == {"shared": "value", "seen_by_m2": True}


def test_dependent_steps_still_run_in_order_under_concurrency(tmp_path: Path) -> None:
    workflow = _workflow(
        [
            StepDefinition(id="a", uses="command", command="echo a"),
            StepDefinition(id="b", uses="command", command="echo b", depends_on=["a"]),
            StepDefinition(id="c", uses="command", command="echo c", depends_on=["b"]),
        ]
    )

    state = run_workflow(
        workflow, tmp_path / "workflow.yaml", tmp_path / "run", max_concurrency=4
    )

    assert state.status == StepStatus.SUCCEEDED
    for step_id in ("a", "b", "c"):
        assert state.steps[step_id].status == StepStatus.SUCCEEDED


# --- Resume --------------------------------------------------------------------


def test_resume_skips_a_previously_succeeded_step(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    workflow_v1 = _workflow(
        [
            StepDefinition(id="a", uses="command", command="echo run >> counter.txt"),
            StepDefinition(id="b", uses="command", command="exit 1", depends_on=["a"]),
        ]
    )

    first_state = run_workflow(workflow_v1, tmp_path / "workflow.yaml", run_dir)

    assert first_state.status == StepStatus.FAILED
    assert first_state.steps["a"].status == StepStatus.SUCCEEDED
    counter_path = run_dir / "steps" / "a" / "counter.txt"
    assert counter_path.read_text().count("run") == 1

    workflow_v2 = _workflow(
        [
            StepDefinition(id="a", uses="command", command="echo run >> counter.txt"),
            StepDefinition(id="b", uses="command", command="echo ok", depends_on=["a"]),
        ]
    )

    second_state = run_workflow(
        workflow_v2, tmp_path / "workflow.yaml", run_dir, resume_state=first_state
    )

    assert second_state.status == StepStatus.SUCCEEDED
    assert second_state.steps["a"].status == StepStatus.SUCCEEDED
    assert second_state.steps["b"].status == StepStatus.SUCCEEDED
    # 'a' was copied over from the prior run, not re-executed.
    assert counter_path.read_text().count("run") == 1


def test_resume_reruns_a_step_that_previously_failed(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    workflow_v1 = _workflow([StepDefinition(id="a", uses="command", command="exit 1")])
    first_state = run_workflow(workflow_v1, tmp_path / "workflow.yaml", run_dir)
    assert first_state.status == StepStatus.FAILED

    workflow_v2 = _workflow([StepDefinition(id="a", uses="command", command="echo ok")])
    second_state = run_workflow(
        workflow_v2, tmp_path / "workflow.yaml", run_dir, resume_state=first_state
    )

    assert second_state.status == StepStatus.SUCCEEDED
    assert second_state.steps["a"].status == StepStatus.SUCCEEDED


def test_resume_with_no_prior_succeeded_steps_behaves_like_a_fresh_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    workflow = _workflow([StepDefinition(id="a", uses="command", command="echo hi")])
    empty_prior = RunState(run_id=run_dir.name, workflow_name="test", workflow_file="workflow.yaml")

    state = run_workflow(workflow, tmp_path / "workflow.yaml", run_dir, resume_state=empty_prior)

    assert state.status == StepStatus.SUCCEEDED
    assert state.steps["a"].status == StepStatus.SUCCEEDED
