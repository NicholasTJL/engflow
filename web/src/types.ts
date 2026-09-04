export type StepUses = "python" | "command" | "template";

export interface StepData {
  uses: StepUses;
  entrypoint?: string;
  command?: string;
  template?: string;
  timeout?: number;
  retries: number;
  [key: string]: unknown;
}

export interface ValidateResponse {
  valid: boolean;
  order: string[] | null;
  error: string | null;
}
