"""engflow command-line interface."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from engflow.core.executor import DEFAULT_MAX_CONCURRENCY, new_run_id, run_workflow
from engflow.core.graph import GraphError, topological_order
from engflow.core.parser import WorkflowParseError, load_workflow
from engflow.core.state import RunState, StepStatus

app = typer.Typer(help="engflow: a lightweight engineering and scientific workflow engine.")

_STATUS_COLOR = {
    StepStatus.SUCCEEDED: typer.colors.GREEN,
    StepStatus.FAILED: typer.colors.RED,
    StepStatus.SKIPPED: typer.colors.YELLOW,
}


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
def run(
    workflow_file: Path,
    run_dir: Annotated[
        Path, typer.Option("--run-dir", help="Directory to store run history under.")
    ] = Path("runs"),
    max_concurrency: Annotated[
        int,
        typer.Option(
            "--max-concurrency", help="Maximum number of steps to run at the same time."
        ),
    ] = DEFAULT_MAX_CONCURRENCY,
    resume: Annotated[
        Path | None,
        typer.Option(
            "--resume",
            help=(
                "A prior run directory to continue. Steps that already succeeded there are "
                "skipped; everything else runs (or re-runs) normally, into the same directory."
            ),
        ),
    ] = None,
) -> None:
    """Execute a workflow, respecting step dependencies, and report the outcome."""
    try:
        workflow = load_workflow(workflow_file)
    except WorkflowParseError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    resume_state = None
    if resume is not None:
        try:
            resume_state = RunState.load(resume)
        except FileNotFoundError as exc:
            typer.secho(str(exc), fg=typer.colors.RED)
            raise typer.Exit(code=1) from exc
        this_run_dir = resume
        typer.echo(f"Resuming: {this_run_dir}")
    else:
        this_run_dir = run_dir / new_run_id()
        typer.echo(f"Run: {this_run_dir}")

    state = run_workflow(
        workflow,
        workflow_file,
        this_run_dir,
        max_concurrency=max_concurrency,
        resume_state=resume_state,
    )

    for step_id, result in state.steps.items():
        color = _STATUS_COLOR.get(result.status, typer.colors.WHITE)
        attempt_note = f" (attempt {result.attempts})" if result.attempts > 1 else ""
        typer.secho(f"  {result.status.value:>9}  {step_id}{attempt_note}", fg=color)
        if result.error:
            typer.secho(f"            {result.error}", fg=typer.colors.RED)

    state_path = this_run_dir / "run_state.json"
    if state.status == StepStatus.FAILED:
        typer.secho(f"Run failed. State: {state_path}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    typer.secho(f"Run succeeded. State: {state_path}", fg=typer.colors.GREEN)


@app.command()
def status(run_dir: Path) -> None:
    """Print the recorded status of a previous run."""
    try:
        state = RunState.load(run_dir)
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Workflow: {state.workflow_name}  ({state.workflow_file})")
    typer.echo(f"Status:   {state.status.value}")
    typer.echo(f"Started:  {state.started_at.isoformat()}")
    if state.finished_at:
        typer.echo(f"Finished: {state.finished_at.isoformat()}")
    for step_id, result in state.steps.items():
        color = _STATUS_COLOR.get(result.status, typer.colors.WHITE)
        attempt_note = f" (attempt {result.attempts})" if result.attempts > 1 else ""
        typer.secho(f"  {result.status.value:>9}  {step_id}{attempt_note}", fg=color)


if __name__ == "__main__":
    app()
