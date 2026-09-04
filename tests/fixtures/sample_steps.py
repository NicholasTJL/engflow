"""Python entrypoint targets used by tests.unit.test_executor."""

from __future__ import annotations

import json
import time
from pathlib import Path


def write_greeting(context: dict) -> None:
    workdir = Path(context["workdir"])
    name = context["parameters"].get("name", "world")
    (workdir / "greeting.txt").write_text(f"hello, {name}\n")
    print(f"wrote greeting for {name}")


def always_fails(context: dict) -> None:
    del context
    raise RuntimeError("this step always fails")


def fail_twice_then_succeed(context: dict) -> None:
    """Fails on its first two calls, succeeds on the third -- proves retries work.

    Uses a counter file under the step's own workdir (stable across
    retries, since the executor reuses the same workdir for every attempt)
    rather than module-level state, so it stays isolated per test.
    """
    workdir = Path(context["workdir"])
    counter_file = workdir / "attempts.txt"
    count = int(counter_file.read_text()) + 1 if counter_file.exists() else 1
    counter_file.write_text(str(count))
    if count < 3:
        raise RuntimeError(f"attempt {count} fails")
    print(f"succeeded on attempt {count}")


def sleep_forever(context: dict) -> None:
    """Never returns on its own -- used to prove PythonRunner enforces a timeout."""
    del context
    time.sleep(30)


def print_env_token(context: dict) -> None:
    """Prints an env value handed via context['env'] -- used for secret-masking tests."""
    print(f"token={context['env'].get('MY_API_TOKEN', '')}")


def record_start_and_end(context: dict) -> None:
    """Sleeps briefly, recording its own start/end time -- used to prove concurrency."""
    workdir = Path(context["workdir"])
    start = time.time()
    time.sleep(0.3)
    end = time.time()
    (workdir / "timing.txt").write_text(f"{start} {end}")


def mutate_parameters_and_record(context: dict) -> None:
    """Mutates context['parameters'] and dumps it -- proves each step gets its own copy.

    If two concurrently running steps shared the same `parameters` dict
    object, one step's mutation would leak into the other's snapshot here.
    """
    workdir = Path(context["workdir"])
    params = context["parameters"]
    params[f"seen_by_{workdir.name}"] = True
    time.sleep(0.2)
    (workdir / "params.json").write_text(json.dumps(params, sort_keys=True))


def print_marker_a(context: dict) -> None:
    """Prints timed 'A's; pairs with print_marker_b in a stdout thread-isolation test."""
    del context
    for _ in range(20):
        print("AAAA", end="")
        time.sleep(0.005)


def print_marker_b(context: dict) -> None:
    """Prints timed 'B's; pairs with print_marker_a in a stdout thread-isolation test."""
    del context
    for _ in range(20):
        print("BBBB", end="")
        time.sleep(0.005)
