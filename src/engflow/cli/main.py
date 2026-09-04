"""engflow command-line interface."""

from __future__ import annotations

from pathlib import Path

import typer

from engflow.core.graph import GraphError, topological_order
from engflow.core.parser import WorkflowParseError, load_workflow

app = typer.Typer(help="engflow: a lightweight engineering and scientific workflow engine.")


@app.command()
def validate(workflow_file: Path) -> None:
    """Validate a workflow file and report errors."""
    try:
        workflow = load_workflow(workflow_file)
        topological_order(workflow)
    except (WorkflowParseError, GraphError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    typer.secho(f"{workflow_file} is valid ({len(workflow.steps)} steps).", fg=typer.colors.GREEN)


@app.command()
def graph(workflow_file: Path) -> None:
    """Print the execution order for a workflow file."""
    try:
        workflow = load_workflow(workflow_file)
        order = topological_order(workflow)
    except (WorkflowParseError, GraphError) as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc
    for index, step_id in enumerate(order, start=1):
        typer.echo(f"{index}. {step_id}")


@app.command()
def run(workflow_file: Path) -> None:
    """Execute a workflow. Not implemented yet — planned for the v0.1.0 release."""
    del workflow_file
    typer.secho("engflow run is not implemented yet — see docs/vision.md.", fg=typer.colors.YELLOW)
    raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
