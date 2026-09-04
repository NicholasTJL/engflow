"""Step implementations for the parameter_sweep example.

Run with (from the repository root):
    engflow run examples/parameter_sweep/workflow.yaml
"""

from __future__ import annotations

import json
from pathlib import Path


def _sibling_step_dir(run_dir: str, step_id: str) -> Path:
    return Path(run_dir) / "steps" / step_id


def generate_inputs(context: dict) -> None:
    angles = context["parameters"]["angle_of_attack"]
    inputs = [{"angle_of_attack": angle} for angle in angles]

    workdir = Path(context["workdir"])
    (workdir / "inputs.json").write_text(json.dumps(inputs, indent=2))
    print(f"generated {len(inputs)} input(s): {inputs}")


def evaluate(context: dict) -> None:
    inputs_path = _sibling_step_dir(context["run_dir"], "generate_inputs") / "inputs.json"
    inputs = json.loads(inputs_path.read_text())

    results = []
    for row in inputs:
        angle = row["angle_of_attack"]
        # A toy lift-coefficient curve -- not a real aerodynamics formula,
        # just enough nonlinearity to make the sweep worth plotting.
        lift_coefficient = round(0.11 * angle - 0.0004 * angle**3, 5)
        results.append({"angle_of_attack": angle, "lift_coefficient": lift_coefficient})

    workdir = Path(context["workdir"])
    (workdir / "results.json").write_text(json.dumps(results, indent=2))
    print(f"evaluated {len(results)} point(s)")


def report(context: dict) -> None:
    results_path = _sibling_step_dir(context["run_dir"], "evaluate") / "results.json"
    results = json.loads(results_path.read_text())

    lines = ["angle_of_attack,lift_coefficient"]
    lines += [f"{row['angle_of_attack']},{row['lift_coefficient']}" for row in results]
    report_text = "\n".join(lines) + "\n"

    workdir = Path(context["workdir"])
    (workdir / "report.csv").write_text(report_text)
    print("wrote report.csv:")
    print(report_text)
