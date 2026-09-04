# Changelog

All notable changes to this project are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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

### Known limitations

- No retries, timeouts, resume, or concurrent step execution yet (v0.2.0).
- No plugin runner protocol, Docker/HTTP runners, or `template` step execution yet (v0.3.0).
