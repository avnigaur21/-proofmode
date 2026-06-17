export type CheckStatus = "passed" | "failed" | "uncertain";
export type RunStatus = "pending" | "running" | "passed" | "failed" | "uncertain";
export type VerificationLayer = "ui" | "api" | "db" | "diff";

export type ProofCheck = {
  layer: VerificationLayer;
  status: CheckStatus;
  summary: string;
  evidence: Record<string, string>;
};

export type ProofRun = {
  id: string;
  claim: string;
  status: RunStatus;
  created_at: string;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  checks: ProofCheck[];
};

