# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Concurrent execution: independent steps now run at the same time via a thread pool, up to
  `--max-concurrency` at once (default 4), instead of strictly one at a time. `RunState` writes
  are serialized under a lock so concurrent step completions can't corrupt `run_state.json`.
- Retries with exponential backoff: `StepDefinition.retries` is now honored. A failed step is
  retried up to `retries` times (backoff 1s, 2s, 4s, ...) before being marked failed.
  `StepResult.attempts` records how many attempts it took.
- Timeout enforcement for `python` steps: `PythonRunner` now respects `StepDefinition.timeout`,
  running the target function in a background thread and giving up after the timeout. (Python
  has no safe way to force-kill a thread, so a timed-out function is abandoned, not stopped --
  documented as a known limitation in the README.)
- Process-tree termination for `command` steps: a timed-out command's whole process tree is
  killed via `psutil`, not just the immediate process, so a shell script's own background
  children no longer survive the step being killed.
- `StepDefinition.env`: per-step environment variables, merged into the subprocess environment
  for `command` steps and exposed via `context["env"]` for `python` steps.
- Secret masking: values from environment variables named `*_KEY`, `*_TOKEN`, `*_SECRET`, or
  `*_PASSWORD` are masked to `***MASKED***` in `stdout.log`, `stderr.log`, and recorded error
  messages (`engflow.core.secrets`). Documented in the README as a best-effort safety net, not a
  guarantee.
- Resume: `engflow run workflow.yaml --resume <run-dir>` continues a prior run in place, skipping
  any step that already succeeded there and re-running everything else. This is a same-run-
  directory check ("did this step succeed here last time"), not content-based caching.
- `engflow run`/`engflow status` now show `(attempt N)` next to a step that needed retries.

### Changed

- `run_workflow()` takes `max_concurrency` and `resume_state` keyword arguments.
- `RunState.save()` writes via a temp file plus atomic rename, instead of writing the JSON file
  directly, to avoid a reader ever seeing a partially written file.

### Known limitations

- No SQLite run history or content-based caching yet (deferred; see docs/vision.md).
- No plugin runner protocol, Docker/HTTP runners, or `template` step execution yet (v0.3.0).

## [0.1.0]

### Added

- Project scaffold: package layout, CI, contribution templates.
- `WorkflowDefinition` / `StepDefinition` schema with validation.
- YAML workflow parser (`engflow.core.parser`).
- Dependency graph builder and cycle detection (`engflow.core.graph`).
- `engflow validate` and `engflow graph` CLI commands.
- FastAPI backend (`engflow.api`) exposing `/validate`, wrapping the same parser/graph logic.
- `engflow studio`: a React Flow visual workflow builder (`web/`).
- Sequential execution engine (`engflow.core.executor`): `python` and `command` runners,
  per-step working directories, captured stdout/stderr, file-based run state.
- `engflow run` and `engflow status` CLI commands.
