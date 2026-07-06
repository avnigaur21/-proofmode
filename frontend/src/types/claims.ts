import type { ProofRun, RunConfiguration } from "./runs";

export type ClaimIngestionCreate = {
  claim: string;
  agent_report?: string | null;
  source?: string;
  agent_name?: string | null;
  project_id?: string | null;
  external_id?: string | null;
  metadata?: Record<string, unknown>;
  raw_payload?: Record<string, unknown>;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  run_config?: RunConfiguration | null;
};

export type IngestedClaim = {
  id: string;
  claim: string;
  source: string;
  agent_name?: string | null;
  project_id?: string | null;
  external_id?: string | null;
  metadata: Record<string, unknown>;
  raw_payload: Record<string, unknown>;
  run_id: string;
  created_at: string;
};

export type ClaimIngestionResponse = {
  claim_record: IngestedClaim;
  run: ProofRun;
};
