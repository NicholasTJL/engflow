"""Python-function step runner.

The target function is called as `function(context)`, where `context` is a
dict with `parameters` (the workflow's top-level parameters), `workdir`
(this step's working directory, as a string), `run_dir` (the run's shared
root, so a step can read a prior step's workdir under
`run_dir/steps/<step_id>/` if it needs to), and `env` (the merged
process-environment-plus-`step.env` dict for this step -- see the module
docstring below for why this isn't just applied to `os.environ`).
"""

from __future__ import annotations

import importlib
import io
import sys
import threading
import traceback
from pathlib import Path
from typing import IO

from engflow.core import secrets
from engflow.core.models import StepDefinition
from engflow.runners.base import RunnerOutcome, StepRunner

# `PythonRunner` never writes to `os.environ`: a step's declared `env` is
# handed to it via `context["env"]` instead. `os.environ` is one table
# shared by the whole process, so if two python steps ran concurrently (as
# the executor now allows) and each temporarily set/restored it around the
# function call, they would stomp on each other's variables mid-run.
# Reading `context["env"]` has no such race.

_thread_output: threading.local = threading.local()
_install_lock = threading.Lock()


class _ThreadLocalStdout:
    """A `sys.stdout` replacement that routes writes to the calling thread's buffer.

    `contextlib.redirect_stdout` swaps the single, process-wide `sys.stdout`
    reference, which is safe for one step running at a time but not for
    several `PythonRunner.run` calls executing concurrently in different
    threads (they'd all be redirecting the same global and clobbering each
    other's captured output). Installing this once and keying the actual
    buffer off `threading.local()` makes capture per-thread instead.
    """

    def __init__(self, fallback: IO[str]) -> None:
        self._fallback = fallback

    def _target(self) -> IO[str]:
        buffer: IO[str] | None = getattr(_thread_output, "buffer", None)
        return buffer if buffer is not None else self._fallback

    def write(self, text: str) -> int:
        return self._target().write(text)

    def flush(self) -> None:
        self._target().flush()

    def isatty(self) -> bool:
        return False


def _install_thread_local_stdout() -> None:
    # Guarded by a lock, not just the isinstance check: if two python steps
    # with no dependency on each other both call this as their very first
    # run, two threads could otherwise race the check and each wrap
    # `sys.stdout` (nesting one `_ThreadLocalStdout` inside another's
    # fallback). Harmless -- writes would still land in the right thread's
    # buffer -- but pointless and easy to just not have happen.
    with _install_lock:
        if not isinstance(sys.stdout, _ThreadLocalStdout):
            sys.stdout = _ThreadLocalStdout(sys.stdout)


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
        env = secrets.step_env(step)
        secret_vals = secrets.secret_values(env)
        context = {
            "parameters": parameters,
            "workdir": str(workdir),
            "run_dir": str(run_dir),
            "env": env,
        }

        try:
            module = importlib.import_module(module_name)
            function = getattr(module, function_name)
        except (ImportError, AttributeError) as exc:
            stderr_path.write_text(secrets.mask(f"{exc}\n", secret_vals), encoding="utf-8")
            error = f"could not resolve entrypoint {step.entrypoint!r}: {exc}"
            return RunnerOutcome(exit_code=1, error=secrets.mask(error, secret_vals))

        _install_thread_local_stdout()
        stdout_buffer = io.StringIO()
        outcome_box: dict[str, BaseException] = {}

        def target() -> None:
            _thread_output.buffer = stdout_buffer
            try:
                function(context)
            except BaseException as exc:  # noqa: BLE001 - reported to the caller, not swallowed
                outcome_box["exception"] = exc
            finally:
                _thread_output.buffer = None

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout=step.timeout)

        if thread.is_alive():
            stdout_path.write_text(
                secrets.mask(stdout_buffer.getvalue(), secret_vals), encoding="utf-8"
            )
            stderr_path.write_text(
                f"step timed out after {step.timeout}s. Python has no safe way to kill a "
                "thread, so the function is still running in the background and will be "
                "abandoned when this process exits.\n",
                encoding="utf-8",
            )
            error = f"step {step.id!r} timed out after {step.timeout}s"
            return RunnerOutcome(exit_code=1, error=secrets.mask(error, secret_vals))

        stdout_path.write_text(
            secrets.mask(stdout_buffer.getvalue(), secret_vals), encoding="utf-8"
        )

        exception = outcome_box.get("exception")
        if exception is not None:
            trace = "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )
            stderr_path.write_text(secrets.mask(trace, secret_vals), encoding="utf-8")
            error = f"{type(exception).__name__}: {exception}"
            return RunnerOutcome(exit_code=1, error=secrets.mask(error, secret_vals))

        stderr_path.write_text("", encoding="utf-8")
        return RunnerOutcome(exit_code=0)
