from pathlib import Path

from engflow.core.executor import run_workflow
from engflow.core.models import StepDefinition, WorkflowDefinition
from engflow.core.state import RunState, StepStatus


def _workflow(
    steps: list[StepDefinition], parameters: dict[str, object] | None = None
) -> WorkflowDefinition:
    return WorkflowDefinition(name="test", parameters=parameters or {}, steps=steps)


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
