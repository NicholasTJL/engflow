import type { Node } from "reactflow";

import type { StepData, StepUses } from "../types";

interface InspectorProps {
  node: Node<StepData> | null;
  onChange: (patch: Partial<StepData>) => void;
  onRename: (newId: string) => void;
}

export default function Inspector({ node, onChange, onRename }: InspectorProps) {
  if (!node) {
    return (
      <aside className="inspector">
        <p className="hint">Select a step on the canvas to edit it.</p>
      </aside>
    );
  }

  return (
    <aside className="inspector">
      <label>
        Step id
        <input
          key={node.id}
          defaultValue={node.id}
          onBlur={(event) => onRename(event.target.value)}
        />
      </label>

      <label>
        Uses
        <select
          value={node.data.uses}
          onChange={(event) => onChange({ uses: event.target.value as StepUses })}
        >
          <option value="python">python</option>
          <option value="command">command</option>
          <option value="template">template</option>
        </select>
      </label>

      {node.data.uses === "python" ? (
        <label>
          Entrypoint
          <input
            value={node.data.entrypoint ?? ""}
            onChange={(event) => onChange({ entrypoint: event.target.value })}
            placeholder="module.path:function_name"
          />
        </label>
      ) : null}

      {node.data.uses === "command" ? (
        <label>
          Command
          <input
            value={node.data.command ?? ""}
            onChange={(event) => onChange({ command: event.target.value })}
            placeholder="python script.py --arg value"
          />
        </label>
      ) : null}

      {node.data.uses === "template" ? (
        <label>
          Template
          <input
            value={node.data.template ?? ""}
            onChange={(event) => onChange({ template: event.target.value })}
            placeholder="templates/report.html"
          />
        </label>
      ) : null}

      <label>
        Retries
        <input
          type="number"
          min={0}
          value={node.data.retries}
          onChange={(event) => onChange({ retries: Number(event.target.value) })}
        />
      </label>

      <label>
        Timeout (seconds)
        <input
          type="number"
          min={0}
          value={node.data.timeout ?? ""}
          onChange={(event) =>
            onChange({ timeout: event.target.value ? Number(event.target.value) : undefined })
          }
        />
      </label>

      <p className="hint">
        Connect steps by dragging from one node's bottom handle to another's top handle. An edge
        A → B means B depends on A.
      </p>
    </aside>
  );
}
