export type CheckStatus = "passed" | "failed" | "uncertain";
export type RunStatus = "pending" | "running" | "passed" | "failed" | "uncertain";
export type ApprovalDecision = "approved" | "rejected" | "fix_requested";
export type EvidenceVerdict = "supported" | "contradicted" | "insufficient";
export type SelfReportVerdict = "aligned" | "partially_unsupported" | "contradicted" | "not_provided";
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type VerificationLayer = "ui" | "api" | "db" | "diff" | "tests";
export type TimelineLayer = "run" | "planner" | "evaluator" | VerificationLayer | "report";

export type RunConfiguration = {
  ui_enabled: boolean;
  api_enabled: boolean;
  db_enabled: boolean;
  diff_enabled: boolean;
  tests_enabled: boolean;
  planner_enabled: boolean;
  approval_required: boolean;
};

export type ClaimSourceMetadata = {
  source: string;
  agent_name?: string | null;
  project_id?: string | null;
  external_id?: string | null;
  metadata: Record<string, unknown>;
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

export type ApiEndpointCheck = {
  name: string;
  method?: string;
  path: string;
  expected_status?: number;
  required_fields?: string[];
};

export type UiFlowStep = {
  action: "click" | "fill" | "expect_text" | "expect_url" | "expect_selector";
  selector?: string | null;
  text?: string | null;
  value?: string | null;
  url_contains?: string | null;
};

export type UiFlowCheck = {
  name: string;
  path?: string | null;
  steps: UiFlowStep[];
};

export type TestCommandCheck = {
  name: string;
  command: string;
  working_directory?: string | null;
  timeout_seconds?: number;
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
  rubrics: EvaluationRubricScore[];
  evaluator_mode: string;
  provider?: string | null;
  model?: string | null;
};

export type SelfReportMismatch = {
  topic: string;
  severity: string;
  agent_statement: string;
  evidence_status: string;
  explanation: string;
};

export type SelfReportComparison = {
  verdict: SelfReportVerdict;
  confidence: number;
  summary: string;
  detected_claims: string[];
  mismatches: SelfReportMismatch[];
  supported_statements: string[];
};

export type EvaluationRubricScore = {
  name: string;
  score: number;
  label: string;
  explanation: string;
};

export type RiskFactor = {
  name: string;
  severity: RiskLevel;
  points: number;
  explanation: string;
};

export type RiskAssessment = {
  level: RiskLevel;
  score: number;
  summary: string;
  factors: RiskFactor[];
  recommended_action: string;
};

export type ProofRun = {
  id: string;
  claim: string;
  status: RunStatus;
  created_at: string;
  agent_report?: string | null;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  api_checks: ApiEndpointCheck[];
  ui_flows: UiFlowCheck[];
  test_commands: TestCommandCheck[];
  run_config: RunConfiguration;
  claim_source: ClaimSourceMetadata;
  checklist: VerificationChecklist;
  checks: ProofCheck[];
  evaluation?: EvidenceEvaluation | null;
  risk?: RiskAssessment | null;
  self_report_comparison?: SelfReportComparison | null;
  timeline: TimelineEvent[];
  approval?: ApprovalRecord | null;
  report_path?: string | null;
  report_url?: string | null;
};

export type ProofRunCreate = {
  claim: string;
  agent_report?: string | null;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  api_checks?: ApiEndpointCheck[];
  ui_flows?: UiFlowCheck[];
  test_commands?: TestCommandCheck[];
  run_config?: RunConfiguration;
  claim_source?: ClaimSourceMetadata;
};

export type ApprovalCreate = {
  decision: ApprovalDecision;
  note?: string | null;
  reviewer?: string | null;
};
