from pathlib import Path

import pytest
from typer.testing import CliRunner

from engflow.cli.main import app

runner = CliRunner()

VALID_WORKFLOW = """
name: demo
steps:
  - id: a
    uses: command
    command: echo a
  - id: b
    uses: command
    command: echo b
    depends_on: [a]
"""

CYCLE_WORKFLOW = """
name: demo
steps:
  - id: a
    uses: command
    command: echo a
    depends_on: [b]
  - id: b
    uses: command
    command: echo b
    depends_on: [a]
"""


def _write(tmp_path: Path, content: str) -> Path:
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(content)
    return workflow_file


def test_validate_valid_workflow(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, VALID_WORKFLOW)

    result = runner.invoke(app, ["validate", str(workflow_file)])

    assert result.exit_code == 0
    assert "is valid" in result.output


def test_validate_cycle_fails(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, CYCLE_WORKFLOW)

    result = runner.invoke(app, ["validate", str(workflow_file)])

    assert result.exit_code == 1
    assert "cycle" in result.output


def test_graph_prints_order(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, VALID_WORKFLOW)

    result = runner.invoke(app, ["graph", str(workflow_file)])

    assert result.exit_code == 0
    assert "1. a" in result.output
    assert "2. b" in result.output


def test_run_succeeds_and_writes_state(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, VALID_WORKFLOW)
    run_dir = tmp_path / "runs"

    result = runner.invoke(app, ["run", str(workflow_file), "--run-dir", str(run_dir)])

    assert result.exit_code == 0
    assert "Run succeeded" in result.output
    state_files = list(run_dir.glob("*/run_state.json"))
    assert len(state_files) == 1


def test_run_reports_failure(tmp_path: Path) -> None:
    workflow_file = _write(
        tmp_path,
        """
name: demo
steps:
  - id: a
    uses: command
    command: exit 1
""",
    )
    run_dir = tmp_path / "runs"

    result = runner.invoke(app, ["run", str(workflow_file), "--run-dir", str(run_dir)])

    assert result.exit_code == 1
    assert "Run failed" in result.output


def test_status_reads_previous_run(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, VALID_WORKFLOW)
    run_dir = tmp_path / "runs"
    runner.invoke(app, ["run", str(workflow_file), "--run-dir", str(run_dir)])
    (this_run,) = run_dir.iterdir()

    result = runner.invoke(app, ["status", str(this_run)])

    assert result.exit_code == 0
    assert "succeeded" in result.output


def test_run_invalid_workflow_fails(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, "name: [unclosed")

    result = runner.invoke(app, ["run", str(workflow_file)])

    assert result.exit_code == 1
    assert "invalid YAML" in result.output


def test_status_missing_run_fails(tmp_path: Path) -> None:
    result = runner.invoke(app, ["status", str(tmp_path / "does-not-exist")])

    assert result.exit_code == 1


def test_run_accepts_max_concurrency_option(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, VALID_WORKFLOW)
    run_dir = tmp_path / "runs"

    result = runner.invoke(
        app, ["run", str(workflow_file), "--run-dir", str(run_dir), "--max-concurrency", "2"]
    )

    assert result.exit_code == 0
    assert "Run succeeded" in result.output


RESUME_WORKFLOW_STEP_B_FAILS = """
name: demo
steps:
  - id: a
    uses: command
    command: echo run >> counter.txt
  - id: b
    uses: command
    command: exit 1
    depends_on: [a]
"""

RESUME_WORKFLOW_STEP_B_SUCCEEDS = """
name: demo
steps:
  - id: a
    uses: command
    command: echo run >> counter.txt
  - id: b
    uses: command
    command: echo ok
    depends_on: [a]
"""


def test_resume_skips_previously_succeeded_step(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, RESUME_WORKFLOW_STEP_B_FAILS)
    run_dir = tmp_path / "runs"

    first = runner.invoke(app, ["run", str(workflow_file), "--run-dir", str(run_dir)])
    assert first.exit_code == 1
    (this_run,) = run_dir.iterdir()
    counter_path = this_run / "steps" / "a" / "counter.txt"
    assert counter_path.read_text().count("run") == 1

    workflow_file.write_text(RESUME_WORKFLOW_STEP_B_SUCCEEDS)
    second = runner.invoke(app, ["run", str(workflow_file), "--resume", str(this_run)])

    assert second.exit_code == 0
    assert "Resuming" in second.output
    assert "Run succeeded" in second.output
    # 'a' was not re-run: still exactly one recorded execution.
    assert counter_path.read_text().count("run") == 1


def test_resume_missing_run_dir_fails(tmp_path: Path) -> None:
    workflow_file = _write(tmp_path, VALID_WORKFLOW)

    result = runner.invoke(app, ["run", str(workflow_file), "--resume", str(tmp_path / "nope")])

    assert result.exit_code == 1


def test_run_shows_attempt_count_when_step_retried(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("engflow.core.executor.time.sleep", lambda _seconds: None)
    workflow_file = _write(
        tmp_path,
        """
name: demo
steps:
  - id: flaky
    uses: python
    entrypoint: tests.fixtures.sample_steps:fail_twice_then_succeed
    retries: 2
""",
    )
    run_dir = tmp_path / "runs"

    result = runner.invoke(app, ["run", str(workflow_file), "--run-dir", str(run_dir)])

    assert result.exit_code == 0
    assert "attempt 3" in result.output
