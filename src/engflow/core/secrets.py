"""Best-effort secret masking for step logs and CLI output.

This is a safety net, not a guarantee. It recognizes a secret only by its
environment-variable NAME: any variable whose name ends in ``_KEY``,
``_TOKEN``, ``_SECRET``, or ``_PASSWORD`` (case-insensitive) is treated as
sensitive, and its VALUE is replaced with ``***MASKED***`` everywhere it
appears verbatim in a step's stdout, stderr, or error message.

Known limits, so nobody relies on this for more than it does:

- It matches on variable *name*, not on the shape of the value. A secret in
  a variable named ``MY_VALUE`` is not masked; a non-secret in a variable
  named ``RETRY_TOKEN`` is masked.
- It only catches the value verbatim. Anything logged base64-encoded,
  URL-encoded, split across log lines, or otherwise transformed slips
  through.
- Values shorter than `_MIN_SECRET_LENGTH` are never masked, because a short
  common value (e.g. ``TOKEN=1``) would otherwise blank out every "1" in a
  step's output.
"""

from __future__ import annotations

import os
import re

from engflow.core.models import StepDefinition

MASK = "***MASKED***"
_MIN_SECRET_LENGTH = 8
_SECRET_NAME = re.compile(r"(_KEY|_TOKEN|_SECRET|_PASSWORD)$", re.IGNORECASE)


def step_env(step: StepDefinition) -> dict[str, str]:
    """The environment a step runs with: the process environment plus `step.env`."""
    return {**os.environ, **step.env}


def secret_values(env: dict[str, str]) -> list[str]:
    """Values from `env` whose variable name looks like a secret.

    Sorted longest-first so masking a longer secret can't be pre-empted by
    a shorter one that happens to be its substring.
    """
    values = {
        value
        for name, value in env.items()
        if value and len(value) >= _MIN_SECRET_LENGTH and _SECRET_NAME.search(name)
    }
    return sorted(values, key=len, reverse=True)


def mask(text: str, values: list[str]) -> str:
    """Replace every occurrence of each value in `values` with `MASK`."""
    for value in values:
        if value:
            text = text.replace(value, MASK)
    return text
