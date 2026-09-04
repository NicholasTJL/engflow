# engflow studio

A visual workflow builder: drag steps onto a canvas, connect dependencies, and validate against
the real `engflow` schema and dependency-graph logic — no mocked backend.

**What "Validate & preview order" actually does**: it sends the current graph to the
`engflow` API, which runs it through the same `WorkflowDefinition` schema and
`topological_order()` function the CLI uses. It reports whether the workflow is valid and, if
so, the computed execution order. The studio itself doesn't execute steps yet (there's no
`/run` endpoint) — `engflow run` is real now, but only via the CLI; export the workflow as
YAML and run it there.

## Run it

You need both the API and this frontend running.

**1. API** (from the repo root):

```bash
pip install -e ".[api]"
uvicorn engflow.api.main:app --reload
```

**2. Frontend** (from this directory):

```bash
npm install
npm run dev
```

Open http://localhost:5173. By default it talks to the API at `http://localhost:8000`; override
with a `VITE_API_BASE` environment variable if you're running the API elsewhere.

## How it works

- Each node is a `StepDefinition` (`uses`, `entrypoint`/`command`/`template`, `retries`,
  `timeout`). Click a node to edit its fields in the side panel.
- An edge from A to B means B depends on A — drag from a node's bottom handle to another's top
  handle to connect them.
- **Load template** loads one of four example workflows onto the canvas (`simple chain`,
  `parameter sweep` — matches `examples/parameter_sweep` in the repo and actually runs via
  `engflow run`, `diamond dependency`, `ML training pipeline`) so a new visitor has something
  concrete to look at instead of a blank canvas. See `src/templates.ts`.
- **Export YAML** downloads the current graph in the exact format `engflow validate` accepts, so
  you can round-trip between the visual builder and the CLI.

## Stack

React + TypeScript + [React Flow](https://reactflow.dev/) for the canvas, plain `fetch` against
the FastAPI backend (`src/engflow/api/main.py`) — no state management library, no CSS framework.
