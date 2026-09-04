"""Direct unit tests for CommandRunner and PythonRunner, bypassing the executor."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import psutil

from engflow.core.models import StepDefinition
from engflow.runners.command import CommandRunner
from engflow.runners.python import PythonRunner


def _workdir(tmp_path: Path, name: str = "workdir") -> Path:
    workdir = tmp_path / name
    workdir.mkdir()
    return workdir


# --- CommandRunner ----------------------------------------------------------


def test_command_runner_requires_command(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    step = StepDefinition(id="s", uses="command")

    outcome = CommandRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 1
    assert "no command set" in (outcome.error or "")


def test_command_runner_injects_step_env(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    script = tmp_path / "print_env.py"
    script.write_text("import os; print(os.environ.get('MY_VAR', ''), end='')")
    step = StepDefinition(
        id="s",
        uses="command",
        command=f'"{sys.executable}" "{script}"',
        env={"MY_VAR": "hello"},
    )

    outcome = CommandRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 0
    assert (workdir / "stdout.log").read_text() == "hello"


def test_command_runner_masks_secret_env_value_in_logs(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    script = tmp_path / "print_env.py"
    script.write_text("import os; print(os.environ.get('MY_API_TOKEN', ''), end='')")
    secret = "sekrit-value-0123456789"
    step = StepDefinition(
        id="s",
        uses="command",
        command=f'"{sys.executable}" "{script}"',
        env={"MY_API_TOKEN": secret},
    )

    outcome = CommandRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 0
    logged = (workdir / "stdout.log").read_text()
    assert secret not in logged
    assert "MASKED" in logged


def test_command_runner_timeout_kills_orphaned_grandchild_process(tmp_path: Path) -> None:
    """A timed-out step's whole process tree is terminated, not just its immediate child.

    `command` here is itself a small script that spawns its own background
    child and then hangs -- mirroring a shell script that forks a
    subprocess. Without process-tree termination, that grandchild would
    survive the parent being killed.
    """
    workdir = _workdir(tmp_path)
    parent_script = tmp_path / "parent.py"
    parent_script.write_text(
        "import subprocess, sys, time\n"
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        "open('child_pid.txt', 'w').write(str(child.pid))\n"
        "time.sleep(30)\n"
    )
    step = StepDefinition(
        id="hang",
        uses="command",
        command=f'"{sys.executable}" "{parent_script}"',
        timeout=1,
    )

    outcome = CommandRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 1
    assert outcome.error is not None
    assert "timed out" in outcome.error

    child_pid = int((workdir / "child_pid.txt").read_text())
    deadline = time.time() + 5
    while psutil.pid_exists(child_pid) and time.time() < deadline:
        time.sleep(0.1)
    assert not psutil.pid_exists(child_pid), "orphaned grandchild process survived the timeout"


def test_command_runner_respects_no_timeout(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    step = StepDefinition(id="s", uses="command", command="echo hi")

    outcome = CommandRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 0


# --- PythonRunner ------------------------------------------------------------


def test_python_runner_requires_entrypoint(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    step = StepDefinition(id="s", uses="python")

    outcome = PythonRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 1
    assert "no entrypoint set" in (outcome.error or "")


def test_python_runner_rejects_malformed_entrypoint(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    step = StepDefinition(id="s", uses="python", entrypoint="not_a_module_colon_function")

    outcome = PythonRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 1
    assert "must be" in (outcome.error or "")


def test_python_runner_reports_unresolvable_entrypoint(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    step = StepDefinition(id="s", uses="python", entrypoint="tests.fixtures.sample_steps:missing")

    outcome = PythonRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 1
    assert "could not resolve entrypoint" in (outcome.error or "")


def test_python_runner_timeout_marks_step_failed(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    step = StepDefinition(
        id="s", uses="python", entrypoint="tests.fixtures.sample_steps:sleep_forever", timeout=1
    )

    outcome = PythonRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 1
    assert outcome.error is not None
    assert "timed out" in outcome.error


def test_python_runner_masks_secret_env_value_in_logs(tmp_path: Path) -> None:
    workdir = _workdir(tmp_path)
    secret = "sekrit-python-abcdefghi"
    step = StepDefinition(
        id="s",
        uses="python",
        entrypoint="tests.fixtures.sample_steps:print_env_token",
        env={"MY_API_TOKEN": secret},
    )

    outcome = PythonRunner().run(step, workdir, {}, tmp_path)

    assert outcome.exit_code == 0
    logged = (workdir / "stdout.log").read_text()
    assert secret not in logged
    assert "MASKED" in logged


def test_python_runner_stdout_is_isolated_per_concurrent_step(tmp_path: Path) -> None:
    """Two PythonRunner.run() calls in different threads must not cross-contaminate stdout.

    `contextlib.redirect_stdout` swaps the single, process-wide sys.stdout,
    which would corrupt one step's captured output with another's if two
    ran at once. PythonRunner routes captured output through per-thread
    buffers instead -- this proves that actually holds under real
    concurrent threads, not just sequential calls.
    """
    workdir_a = _workdir(tmp_path, "a")
    workdir_b = _workdir(tmp_path, "b")
    step_a = StepDefinition(
        id="a", uses="python", entrypoint="tests.fixtures.sample_steps:print_marker_a"
    )
    step_b = StepDefinition(
        id="b", uses="python", entrypoint="tests.fixtures.sample_steps:print_marker_b"
    )
    runner = PythonRunner()
    results: dict[str, object] = {}

    def call(name: str, step: StepDefinition, workdir: Path) -> None:
        results[name] = runner.run(step, workdir, {}, tmp_path)

    thread_a = threading.Thread(target=call, args=("a", step_a, workdir_a))
    thread_b = threading.Thread(target=call, args=("b", step_b, workdir_b))
    thread_a.start()
    thread_b.start()
    thread_a.join()
    thread_b.join()

    assert (workdir_a / "stdout.log").read_text() == "AAAA" * 20
    assert (workdir_b / "stdout.log").read_text() == "BBBB" * 20
