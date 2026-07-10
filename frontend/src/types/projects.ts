import type { ApiEndpointCheck, RunConfiguration, UiFlowCheck } from "./runs";

export type ProjectProfile = {
  id: string;
  name: string;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  api_checks: ApiEndpointCheck[];
  ui_flows: UiFlowCheck[];
  default_run_config: RunConfiguration;
  created_at: string;
  updated_at: string;
};

export type ProjectProfileCreate = {
  name: string;
  repo_path?: string | null;
  target_url?: string | null;
  api_base_url?: string | null;
  target_db_url?: string | null;
  api_checks?: ApiEndpointCheck[];
  ui_flows?: UiFlowCheck[];
  default_run_config: RunConfiguration;
};

export type ProjectProfileUpdate = Partial<ProjectProfileCreate>;
