import type { ValidateResponse } from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

export async function validateWorkflow(payload: unknown): Promise<ValidateResponse> {
  const response = await fetch(`${API_BASE}/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`engflow API returned ${response.status}`);
  }

  return (await response.json()) as ValidateResponse;
}
