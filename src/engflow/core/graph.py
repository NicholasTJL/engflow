"""Build a dependency graph from a workflow and compute a valid execution order."""

from __future__ import annotations

from collections import defaultdict, deque

from engflow.core.models import WorkflowDefinition


class GraphError(Exception):
    """Raised for unknown dependencies or cycles in a workflow's step graph."""


def build_graph(workflow: WorkflowDefinition) -> dict[str, list[str]]:
    """Return an adjacency list mapping each step id to the steps that depend on it."""
    step_ids = {step.id for step in workflow.steps}
    edges: dict[str, list[str]] = defaultdict(list)

    for step in workflow.steps:
        for dependency in step.depends_on:
            if dependency not in step_ids:
                raise GraphError(f"step {step.id!r} depends on unknown step {dependency!r}")
            edges[dependency].append(step.id)

    return dict(edges)


def topological_order(workflow: WorkflowDefinition) -> list[str]:
    """Return step ids in an order that respects all `depends_on` relationships."""
    graph = build_graph(workflow)
    in_degree = {step.id: len(step.depends_on) for step in workflow.steps}

    queue = deque(sorted(step_id for step_id, degree in in_degree.items() if degree == 0))
    order: list[str] = []

    while queue:
        current = queue.popleft()
        order.append(current)
        for neighbour in sorted(graph.get(current, [])):
            in_degree[neighbour] -= 1
            if in_degree[neighbour] == 0:
                queue.append(neighbour)

    if len(order) != len(workflow.steps):
        remaining = sorted(set(in_degree) - set(order))
        raise GraphError(f"workflow contains a cycle involving steps: {remaining}")

    return order
