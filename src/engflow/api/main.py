"""HTTP API exposing engflow's parser and graph logic to the web studio.

This wraps the existing engflow.core validation and graph logic; it does not
duplicate it. Both schema failures (bad `uses`, duplicate ids) and graph
failures (unknown dependency, cycle) come back through the same
`ValidateResponse` shape so the frontend only has one response contract to
handle.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel

from engflow import __version__
from engflow.core.graph import GraphError, topological_order
from engflow.core.models import WorkflowDefinition

app = FastAPI(title="engflow API", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ValidateResponse(BaseModel):
    valid: bool
    order: list[str] | None = None
    error: str | None = None


@app.exception_handler(RequestValidationError)
def handle_schema_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    messages = [
        f"{'.'.join(str(part) for part in error['loc'][1:])}: {error['msg']}"
        for error in exc.errors()
    ]
    body = ValidateResponse(valid=False, error="; ".join(messages))
    return JSONResponse(status_code=200, content=body.model_dump())


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    """This is a JSON API with no landing page -- send visitors to the interactive docs."""
    return RedirectResponse(url="/docs")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/validate", response_model=ValidateResponse)
def validate_workflow(workflow: WorkflowDefinition) -> ValidateResponse:
    try:
        order = topological_order(workflow)
    except GraphError as exc:
        return ValidateResponse(valid=False, error=str(exc))
    return ValidateResponse(valid=True, order=order)
