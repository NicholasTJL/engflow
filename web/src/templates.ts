import type { Edge, Node } from "reactflow";

import type { StepData } from "./types";

export interface WorkflowTemplate {
  id: string;
  label: string;
  description: string;
  workflowName: string;
  nodes: Node<StepData>[];
  edges: Edge[];
}

function node(id: string, x: number, y: number, data: StepData): Node<StepData> {
  return { id, type: "step", position: { x, y }, data };
}

function edge(source: string, target: string): Edge {
  return { id: `${source}-${target}`, source, target };
}

export const TEMPLATES: WorkflowTemplate[] = [
  {
    id: "simple-chain",
    label: "Simple chain",
    description: "Two command steps, one depends on the other -- the smallest useful workflow.",
    workflowName: "simple-chain",
    nodes: [
      node("generate", 120, 80, { uses: "command", command: "python generate.py", retries: 0 }),
      node("process", 120, 240, { uses: "command", command: "python process.py", retries: 0 }),
    ],
    edges: [edge("generate", "process")],
  },
  {
    id: "parameter-sweep",
    label: "Parameter sweep",
    description:
      "Generate inputs, evaluate each one, then report -- matches examples/parameter_sweep in the repo, runnable with engflow run.",
    workflowName: "parameter-sweep",
    nodes: [
      node("generate_inputs", 120, 60, {
        uses: "python",
        entrypoint: "examples.parameter_sweep.steps:generate_inputs",
        retries: 0,
      }),
      node("evaluate", 120, 220, {
        uses: "python",
        entrypoint: "examples.parameter_sweep.steps:evaluate",
        retries: 0,
      }),
      node("report", 120, 380, {
        uses: "python",
        entrypoint: "examples.parameter_sweep.steps:report",
        retries: 0,
      }),
    ],
    edges: [edge("generate_inputs", "evaluate"), edge("evaluate", "report")],
  },
  {
    id: "diamond",
    label: "Diamond dependency",
    description:
      "Two independent branches converge on a final step -- shows how engflow orders steps that don't depend on each other.",
    workflowName: "diamond-dependency",
    nodes: [
      node("fetch_data", 220, 40, { uses: "command", command: "python fetch_data.py", retries: 0 }),
      node("analyze_a", 80, 200, { uses: "command", command: "python analyze_a.py", retries: 0 }),
      node("analyze_b", 360, 200, { uses: "command", command: "python analyze_b.py", retries: 0 }),
      node("combine", 220, 360, { uses: "command", command: "python combine.py", retries: 0 }),
    ],
    edges: [
      edge("fetch_data", "analyze_a"),
      edge("fetch_data", "analyze_b"),
      edge("analyze_a", "combine"),
      edge("analyze_b", "combine"),
    ],
  },
  {
    id: "ml-pipeline",
    label: "ML training pipeline",
    description: "Load data, train a model, evaluate it, and generate a report -- with a retry on the training step.",
    workflowName: "ml-training-pipeline",
    nodes: [
      node("load_data", 120, 40, { uses: "command", command: "python load_data.py", retries: 0 }),
      node("train_model", 120, 200, {
        uses: "command",
        command: "python train.py",
        retries: 1,
        timeout: 3600,
      }),
      node("evaluate_model", 120, 360, {
        uses: "command",
        command: "python evaluate.py",
        retries: 0,
      }),
      node("generate_report", 120, 520, {
        uses: "template",
        template: "templates/report.html",
        retries: 0,
      }),
    ],
    edges: [
      edge("load_data", "train_model"),
      edge("train_model", "evaluate_model"),
      edge("evaluate_model", "generate_report"),
    ],
  },
];
