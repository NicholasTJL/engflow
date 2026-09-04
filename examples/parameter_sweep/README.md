# Example: Parameter Sweep

A three-step workflow: generate inputs, evaluate a function over them, report the results.

The runner (`engflow run`) isn't implemented yet — for now this example demonstrates schema
validation and dependency ordering:

```bash
engflow validate examples/parameter_sweep/workflow.yaml
engflow graph examples/parameter_sweep/workflow.yaml
```
