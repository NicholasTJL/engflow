"""Load and validate workflow YAML files into WorkflowDefinition objects."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from engflow.core.models import WorkflowDefinition


class WorkflowParseError(Exception):
    """Raised when a workflow file cannot be parsed or fails schema validation."""


def load_workflow(path: str | Path) -> WorkflowDefinition:
    path = Path(path)
    if not path.exists():
        raise WorkflowParseError(f"workflow file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise WorkflowParseError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise WorkflowParseError(f"{path} must contain a YAML mapping at the top level")

    try:
        return WorkflowDefinition.model_validate(raw)
    except ValidationError as exc:
        raise WorkflowParseError(f"invalid workflow definition in {path}:\n{exc}") from exc
