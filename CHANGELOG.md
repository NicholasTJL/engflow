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

### Known limitations

- `engflow run` is not implemented yet — execution lands in v0.1.0 (see [docs/vision.md](docs/vision.md)).
