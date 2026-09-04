# Contributing to engflow

engflow is a pre-1.0 project. The core schema and executor interfaces are still settling, so
please open an issue before starting large changes — small fixes and tests are always welcome
without one.

## Setup

```bash
git clone https://github.com/NicholasTJL/engflow.git
cd engflow
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check .
mypy src
pytest --cov=engflow
```

All three must pass. New behavior needs a test; bug fixes need a regression test.

## Scope

The current milestone is `v0.1.0` (see [docs/vision.md](docs/vision.md) for scope and
non-goals). Features outside that scope are welcome as discussion issues but may be deferred.

## Good first issues

Issues labeled `good first issue` are self-contained and don't require familiarity with the
executor internals. `help wanted` issues are open for anyone.

## Code style

- Type hints on all public functions and classes.
- No bare `except:` — catch specific exceptions and raise a project exception type
  (`WorkflowParseError`, `GraphError`, etc.) with a message that names the offending step or file.
- Keep the public API in `engflow.core` and `engflow.cli` stable; internal helpers can change
  freely.
