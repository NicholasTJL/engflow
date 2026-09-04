"""Vercel serverless entrypoint.

Vercel's Python runtime auto-detects an ASGI app by scanning `/api` for a
top-level `app` variable. The real implementation lives in
`engflow.api.main` (see src/engflow/api/main.py) so the CLI, local
`uvicorn` usage, and this deployment all share the exact same code path.
"""

from engflow.api.main import app

__all__ = ["app"]
