export type CheckStatus = "passed" | "failed" | "uncertain";
export type RunStatus = "pending" | "running" | "passed" | "failed" | "uncertain";
export type ApprovalDecision = "approved" | "rejected" | "fix_requested";
export type EvidenceVerdict = "supported" | "contradicted" | "insufficient";
export type VerificationLayer = "ui" | "api" | "db" | "diff";
export type TimelineLayer = "run" | "planner" | "evaluator" | VerificationLayer | "report";

export type RunConfiguration = {
  ui_enabled: boolean;
  api_enabled: boolean;
  db_enabled: boolean;
  diff_enabled: boolean;
  planner_enabled: boolean;
  approval_required: boolean;
};

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
  assertions?: Record<string, unknown>;
};

export type VerificationChecklist = {
  checks: PlannedCheck[];
  affected_files_hint: string[];
  planner?: {
    mode: string;
    source: string;
    provider?: string | null;
    model?: string | null;
    used_fallback: boolean;
    reason?: string | null;
    diff_files_used: number;
    diff_truncated: boolean;
  };
};

export type TimelineEvent = {
  timestamp: string;
  type: string;
  layer: TimelineLayer;
  status?: string | null;
  message: string;
  evidence: Record<string, unknown>;
  metadata: Record<string, unknown>;
};

export type ApprovalRecord = {
  decision: ApprovalDecision;
  note?: string | null;
  reviewer?: string | null;
  decided_at: string;
};

export type EvidenceEvaluation = {
  verdict: EvidenceVerdict;
  confidence: number;
  explanation: string;
  reasons: string[];
  guardrails: string[];
  evaluator_mode: string;
  provider?: string | null;
  model?: string | null;
};

export type ProofRun = {
  id: string;
  claim: string;
  status: RunStatus;
  created_at: string;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  run_config: RunConfiguration;
  checklist: VerificationChecklist;
  checks: ProofCheck[];
  evaluation?: EvidenceEvaluation | null;
  timeline: TimelineEvent[];
  approval?: ApprovalRecord | null;
  report_path?: string | null;
  report_url?: string | null;
};

export type ProofRunCreate = {
  claim: string;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  run_config?: RunConfiguration;
};

export type ApprovalCreate = {
  decision: ApprovalDecision;
  note?: string | null;
  reviewer?: string | null;
};
