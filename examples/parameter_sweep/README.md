# Example: Parameter Sweep

A three-step workflow: generate inputs over a sweep of angle-of-attack values, evaluate a toy
lift-coefficient formula at each one, and write a CSV report. Each step is a plain Python
function in [`steps.py`](steps.py) — see there for how a step reads a prior step's output via
`context["run_dir"]`.

```bash
engflow validate examples/parameter_sweep/workflow.yaml
engflow graph examples/parameter_sweep/workflow.yaml
engflow run examples/parameter_sweep/workflow.yaml
```

`engflow run` prints the run directory (`runs/<run-id>/`); the final report is at
`runs/<run-id>/steps/report/report.csv`.
