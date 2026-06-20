export type CheckStatus = "passed" | "failed" | "uncertain";
export type RunStatus = "pending" | "running" | "passed" | "failed" | "uncertain";
export type VerificationLayer = "ui" | "api" | "db" | "diff";

export type ProofCheck = {
  layer: VerificationLayer;
  status: CheckStatus;
  summary: string;
  evidence: Record<string, unknown>;
};

export type PlannedCheck = {
  layer: VerificationLayer;
  type: string;
  description: string;
  target?: string | null;
};

export type VerificationChecklist = {
  checks: PlannedCheck[];
  affected_files_hint: string[];
};

export type ProofRun = {
  id: string;
  claim: string;
  status: RunStatus;
  created_at: string;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  checklist: VerificationChecklist;
  checks: ProofCheck[];
  report_path?: string | null;
};
