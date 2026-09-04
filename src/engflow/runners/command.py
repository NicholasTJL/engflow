"""Command-line step runner."""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path

import psutil

from engflow.core import secrets
from engflow.core.models import StepDefinition
from engflow.runners.base import RunnerOutcome, StepRunner

_KILL_WAIT_SECONDS = 5


def _kill_process_tree(pid: int) -> None:
    """Kill `pid` and every descendant it has spawned.

    `subprocess`'s own timeout handling only kills the one process it
    started (the shell, when `shell=True`) -- any children that process
    forked (a script starting a background job, for example) are left
    running. This walks the live process tree via psutil, which uses the
    right mechanism per platform (process listing on POSIX, the Windows
    process/thread snapshot API on Windows), and kills every process in it.
    """
    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        return

    children = parent.children(recursive=True)
    for child in children:
        with contextlib.suppress(psutil.NoSuchProcess):
            child.kill()
    with contextlib.suppress(psutil.NoSuchProcess):
        parent.kill()

    psutil.wait_procs([parent, *children], timeout=_KILL_WAIT_SECONDS)


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
        env = secrets.step_env(step)
        secret_vals = secrets.secret_values(env)

        timed_out = False
        # The child process writes to these file descriptors directly, so
        # this encoding only governs the (empty) truncation write Python
        # itself does on open -- not what bytes the child ends up writing.
        with (
            stdout_path.open("w", encoding="utf-8") as stdout_file,
            stderr_path.open("w", encoding="utf-8") as stderr_file,
        ):
            process = subprocess.Popen(
                step.command,
                shell=True,
                cwd=workdir,
                stdout=stdout_file,
                stderr=stderr_file,
                env=env,
            )
            try:
                process.wait(timeout=step.timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_process_tree(process.pid)
                process.wait()

        if secret_vals:
            # The child process wrote these bytes directly to the file
            # descriptor (not through Python's text layer), so they might
            # not be valid UTF-8 -- read leniently rather than crash a
            # masking pass on a command's raw output.
            stdout_text = stdout_path.read_text(encoding="utf-8", errors="replace")
            stderr_text = stderr_path.read_text(encoding="utf-8", errors="replace")
            stdout_path.write_text(secrets.mask(stdout_text, secret_vals), encoding="utf-8")
            stderr_path.write_text(secrets.mask(stderr_text, secret_vals), encoding="utf-8")

        if timed_out:
            error = f"step {step.id!r} timed out after {step.timeout}s; process tree terminated"
            return RunnerOutcome(exit_code=1, error=secrets.mask(error, secret_vals))

        if process.returncode != 0:
            error = f"command exited with status {process.returncode}; see stderr.log"
            return RunnerOutcome(
                exit_code=process.returncode, error=secrets.mask(error, secret_vals)
            )
        return RunnerOutcome(exit_code=0)
