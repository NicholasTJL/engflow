import pytest

from engflow.core.graph import GraphError, topological_order
from engflow.core.models import StepDefinition, WorkflowDefinition


def _workflow(steps: list[StepDefinition]) -> WorkflowDefinition:
    return WorkflowDefinition(name="test", steps=steps)


def test_topological_order_respects_dependencies() -> None:
    workflow = _workflow(
        [
            StepDefinition(id="c", uses="command", command="echo c", depends_on=["b"]),
            StepDefinition(id="a", uses="command", command="echo a"),
            StepDefinition(id="b", uses="command", command="echo b", depends_on=["a"]),
        ]
    )

    order = topological_order(workflow)

    assert order.index("a") < order.index("b") < order.index("c")


def test_unknown_dependency_raises() -> None:
    workflow = _workflow(
        [StepDefinition(id="a", uses="command", command="echo a", depends_on=["missing"])]
    )

    with pytest.raises(GraphError, match="unknown step"):
        topological_order(workflow)


def test_cycle_raises() -> None:
    workflow = _workflow(
        [
            StepDefinition(id="a", uses="command", command="echo a", depends_on=["b"]),
            StepDefinition(id="b", uses="command", command="echo b", depends_on=["a"]),
        ]
    )

    with pytest.raises(GraphError, match="cycle"):
        topological_order(workflow)
