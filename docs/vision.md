# Product Vision and Non-Goals

## Problem

Engineering and scientific work is usually a chain of heterogeneous steps — generate geometry,
mesh it, run a solver, post-process, report — glued together with shell scripts or notebooks
that don't track what ran, in what order, with what inputs, or whether it can be resumed after
a crash. engflow is a small orchestration layer for that chain: define the steps and their
dependencies in YAML, and get validation, execution, logging, and resumability without
adopting a full workflow platform.

## Who it's for

Engineers and researchers who run multi-step computational pipelines (CFD/FEA, CAD/meshing,
parameter sweeps, ML training, lab automation, report generation) and currently manage them
with ad hoc scripts.

## What makes it different

engflow is deliberately general-purpose and lightweight: no cluster, no server, no cloud
dependency. It runs on a laptop as easily as a CI runner, and it doesn't assume any particular
solver, industry, or file format.

## v0.1.0 scope

- YAML workflow definition, parsed into a validated schema.
- Directed acyclic graph construction with cycle detection.
- Sequential execution of Python-function and command-line steps.
- Per-step working directories, captured stdout/stderr, structured logs.
- File-based run state and output artifact registration.
- A CLI: `validate`, `graph`, `run`, `status`, `resume`, `cancel`.

## v0.1.0 non-goals

These are excluded from the first release to protect delivery speed and API quality — not
ruled out permanently:

- Kubernetes or distributed cluster execution.
- Full cloud resource management.
- Enterprise authentication.
- A graphical workflow editor.
- Built-in integrations for every engineering tool.
- A general autonomous agent.
- An embedded optimisation framework (see the separate `optimise-anything` project).
- Replacing a full data-orchestration platform (Airflow, Prefect, etc.).

## Current status

Schema, parser, graph builder, and a concurrent execution engine (`python` and `command`
runners, run state persistence, `engflow run`/`status`) are in place. v0.2.0 landed retries with
exponential backoff, timeout enforcement for both runners (with real process-tree termination
for `command` steps), concurrent execution of independent steps behind `--max-concurrency`,
per-step environment variables with best-effort secret masking in logs, and resume (skip steps
that already succeeded in a given run directory).

Not yet built: SQLite run history and content-based caching (a step re-run only because its run
directory is new, even though its inputs are unchanged, still re-executes today) -- both
deferred, not scoped for a specific release yet. Also deferred: the plugin runner protocol,
Docker/HTTP runners, human-approval steps, the web dashboard, event hooks, and JSON/HTML run
reports (v0.3.0).
