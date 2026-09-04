import { useCallback, useMemo, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
} from "reactflow";
import yaml from "js-yaml";

import { validateWorkflow } from "./api";
import Inspector from "./components/Inspector";
import StepNode from "./components/StepNode";
import { TEMPLATES } from "./templates";
import type { StepData } from "./types";

const nodeTypes = { step: StepNode };

function makeNode(position: { x: number; y: number }): Node<StepData> {
  const id = `step_${crypto.randomUUID().slice(0, 8)}`;
  return {
    id,
    type: "step",
    position,
    data: { uses: "command", command: "echo hello", retries: 0 },
  };
}

interface ValidationState {
  valid: boolean;
  message: string;
  order?: string[];
}

export default function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState<StepData>([makeNode({ x: 100, y: 80 })]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [result, setResult] = useState<ValidationState | null>(null);
  const [workflowName, setWorkflowName] = useState("demo-workflow");

  const selectedNode = useMemo(
    () => nodes.find((node) => node.id === selectedId) ?? null,
    [nodes, selectedId],
  );

  const onConnect = useCallback(
    (connection: Connection) => setEdges((current) => addEdge(connection, current)),
    [setEdges],
  );

  const addStep = useCallback(() => {
    setNodes((current) => [
      ...current,
      makeNode({ x: 100 + (current.length % 4) * 160, y: 80 + Math.floor(current.length / 4) * 120 }),
    ]);
  }, [setNodes]);

  const updateSelected = useCallback(
    (patch: Partial<StepData>) => {
      if (!selectedId) return;
      setNodes((current) =>
        current.map((node) =>
          node.id === selectedId ? { ...node, data: { ...node.data, ...patch } } : node,
        ),
      );
    },
    [selectedId, setNodes],
  );

  const renameSelected = useCallback(
    (newId: string) => {
      const trimmed = newId.trim();
      if (!selectedId || !trimmed || trimmed === selectedId) return;
      if (nodes.some((node) => node.id === trimmed)) return;

      setNodes((current) => current.map((node) => (node.id === selectedId ? { ...node, id: trimmed } : node)));
      setEdges((current) =>
        current.map((edge) => ({
          ...edge,
          source: edge.source === selectedId ? trimmed : edge.source,
          target: edge.target === selectedId ? trimmed : edge.target,
        })),
      );
      setSelectedId(trimmed);
    },
    [selectedId, nodes, setNodes, setEdges],
  );

  const toPayload = useCallback(() => {
    const steps = nodes.map((node) => ({
      id: node.id,
      uses: node.data.uses,
      entrypoint: node.data.uses === "python" ? node.data.entrypoint || undefined : undefined,
      command: node.data.uses === "command" ? node.data.command || undefined : undefined,
      template: node.data.uses === "template" ? node.data.template || undefined : undefined,
      depends_on: edges.filter((edge) => edge.target === node.id).map((edge) => edge.source),
      retries: node.data.retries,
      timeout: node.data.timeout,
    }));
    return { name: workflowName, steps };
  }, [nodes, edges, workflowName]);

  const handleValidate = useCallback(async () => {
    setResult(null);
    try {
      const response = await validateWorkflow(toPayload());
      if (response.valid) {
        setResult({ valid: true, message: "Workflow is valid.", order: response.order ?? undefined });
      } else {
        setResult({ valid: false, message: response.error ?? "Unknown validation error." });
      }
    } catch (error) {
      setResult({
        valid: false,
        message:
          error instanceof Error
            ? `${error.message} — is the API running? (uvicorn engflow.api.main:app)`
            : String(error),
      });
    }
  }, [toPayload]);

  const handleLoadTemplate = useCallback(
    (templateId: string) => {
      const template = TEMPLATES.find((candidate) => candidate.id === templateId);
      if (!template) return;
      setNodes(template.nodes.map((node) => ({ ...node, data: { ...node.data } })));
      setEdges(template.edges.map((edge) => ({ ...edge })));
      setWorkflowName(template.workflowName);
      setSelectedId(null);
      setResult(null);
    },
    [setNodes, setEdges],
  );

  const handleExportYaml = useCallback(() => {
    const text = yaml.dump(toPayload(), { skipInvalid: true });
    const blob = new Blob([text], { type: "text/yaml" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${workflowName}.yaml`;
    anchor.click();
    URL.revokeObjectURL(url);
  }, [toPayload, workflowName]);

  const orderIndex = useMemo(() => {
    const map = new Map<string, number>();
    result?.order?.forEach((id, index) => map.set(id, index + 1));
    return map;
  }, [result]);

  const decoratedNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        data: { ...node.data, orderLabel: orderIndex.get(node.id) },
      })),
    [nodes, orderIndex],
  );

  return (
    <div className="app">
      <header className="toolbar">
        <input
          id="workflow-name"
          name="workflow-name"
          value={workflowName}
          onChange={(event) => setWorkflowName(event.target.value)}
          aria-label="Workflow name"
        />
        <button onClick={addStep}>Add step</button>
        <button onClick={handleValidate}>Validate &amp; preview order</button>
        <button onClick={handleExportYaml}>Export YAML</button>
        <select
          aria-label="Load template"
          defaultValue=""
          onChange={(event) => {
            if (event.target.value) handleLoadTemplate(event.target.value);
            event.target.value = "";
          }}
        >
          <option value="" disabled>
            Load template…
          </option>
          {TEMPLATES.map((template) => (
            <option key={template.id} value={template.id} title={template.description}>
              {template.label}
            </option>
          ))}
        </select>
        <div className="spacer" />
      </header>
      <div className="body">
        <div className="canvas">
          <ReactFlow
            nodes={decoratedNodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_event, node) => setSelectedId(node.id)}
            fitView
          >
            <Background />
            <Controls />
            <MiniMap />
          </ReactFlow>
        </div>
        <Inspector node={selectedNode} onChange={updateSelected} onRename={renameSelected} />
      </div>
      {result ? (
        <footer className={`result ${result.valid ? "valid" : "invalid"}`}>
          <strong>{result.valid ? "Valid" : "Invalid"}:</strong> {result.message}
          {result.order ? <span> — execution order: {result.order.join(" → ")}</span> : null}
        </footer>
      ) : null}
    </div>
  );
}
