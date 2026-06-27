export type SettingsStatus = {
  backend_status: string;
  planner_mode: string;
  llm_provider: string;
  llm_model: string;
  openai_api_key_configured: boolean;
  artifact_root: string;
  run_persistence_enabled: boolean;
  runs_directory: string;
};
