import { Handle, Position, type NodeProps } from "reactflow";

import type { StepData } from "../types";

export default function StepNode({ id, data }: NodeProps<StepData>) {
  return (
    <div className={`step-node step-node--${data.uses}`}>
      <Handle type="target" position={Position.Top} />
      <div className="step-node__id">{id}</div>
      <div className="step-node__uses">{data.uses}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}
