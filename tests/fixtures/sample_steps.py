"""Python entrypoint targets used by tests.unit.test_executor."""

from __future__ import annotations

from pathlib import Path


def write_greeting(context: dict) -> None:
    workdir = Path(context["workdir"])
    name = context["parameters"].get("name", "world")
    (workdir / "greeting.txt").write_text(f"hello, {name}\n")
    print(f"wrote greeting for {name}")


def always_fails(context: dict) -> None:
    del context
    raise RuntimeError("this step always fails")
