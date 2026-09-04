from pathlib import Path

import pytest

from engflow.core.parser import WorkflowParseError, load_workflow


def test_load_valid_workflow(tmp_path: Path) -> None:
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(
        """
name: demo
steps:
  - id: a
    uses: python
    entrypoint: pkg.mod:func
  - id: b
    uses: command
    command: echo hi
    depends_on: [a]
"""
    )

    workflow = load_workflow(workflow_file)

    assert workflow.name == "demo"
    assert [step.id for step in workflow.steps] == ["a", "b"]


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(WorkflowParseError, match="not found"):
        load_workflow(tmp_path / "missing.yaml")


def test_invalid_yaml_raises(tmp_path: Path) -> None:
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text("name: [unclosed")

    with pytest.raises(WorkflowParseError, match="invalid YAML"):
        load_workflow(workflow_file)


def test_duplicate_step_ids_raises(tmp_path: Path) -> None:
    workflow_file = tmp_path / "workflow.yaml"
    workflow_file.write_text(
        """
name: demo
steps:
  - id: a
    uses: python
    entrypoint: pkg.mod:func
  - id: a
    uses: python
    entrypoint: pkg.mod:func
"""
    )

    with pytest.raises(WorkflowParseError, match="duplicate step ids"):
        load_workflow(workflow_file)
