import {
  AlertTriangle,
  ClipboardCheck,
  Copy,
  Database,
  GitBranch,
  Globe2,
  KeyRound,
  MonitorCheck,
  Plus,
  Save,
  Search,
  Server,
  Settings2,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { RunCard } from "../components/RunCard";
import { RunDetail } from "../components/RunDetail";
import {
  createProject,
  createRun,
  deleteProject,
  getSettingsStatus,
  listProjects,
  listRuns,
  seedDemoRuns,
  updateProject,
} from "../services/proofmodeApi";
import type { ProjectProfile } from "../types/projects";
import type { ProofRun, ProofRunCreate, RunConfiguration } from "../types/runs";
import type { SettingsStatus } from "../types/settings";

export function App() {
  const [claim, setClaim] = useState("I added the first ProofMode verification loop");
  const [targetUrl, setTargetUrl] = useState("http://localhost:5173");
  const [apiBaseUrl, setApiBaseUrl] = useState("http://localhost:8000/health");
  const [repoPath, setRepoPath] = useState("");
  const [targetDbUrl, setTargetDbUrl] = useState("");
  const [runConfig, setRunConfig] = useState<RunConfiguration>(defaultRunConfig);
  const [projectName, setProjectName] = useState("ProofMode local");
  const [projects, setProjects] = useState<ProjectProfile[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [isSavingProject, setIsSavingProject] = useState(false);
  const [runs, setRuns] = useState<ProofRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);
  const [runSearch, setRunSearch] = useState("");
  const [showAllRuns, setShowAllRuns] = useState(false);
  const [settingsStatus, setSettingsStatus] = useState<SettingsStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns()
      .then((loadedRuns) => {
        setRuns(loadedRuns);
        setSelectedRunId((current) => current ?? loadedRuns[0]?.id ?? null);
      })
      .catch(() => setError("Backend is not reachable yet."));

    getSettingsStatus()
      .then(setSettingsStatus)
      .catch(() => setSettingsStatus(null));

    listProjects()
      .then((loadedProjects) => {
        setProjects(loadedProjects);
        if (loadedProjects[0]) {
          applyProject(loadedProjects[0]);
        }
      })
      .catch(() => setProjects([]));
  }, []);

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null;
  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const filteredRuns = filterRuns(runs, runSearch);
  const visibleRuns = showAllRuns ? filteredRuns : filteredRuns.slice(0, 4);
  const hiddenRunCount = filteredRuns.length - visibleRuns.length;
  const runCounts = {
    passed: runs.filter((run) => run.status === "passed").length,
    failed: runs.filter((run) => run.status === "failed").length,
    uncertain: runs.filter((run) => run.status === "uncertain").length,
  };
  const runValidationIssues = getRunValidationIssues({
    apiBaseUrl,
    repoPath,
    runConfig,
    targetDbUrl,
    targetUrl,
  });
  const canSubmitRun = claim.trim().length > 0 && runValidationIssues.length === 0;
  const activePresetId = getActivePresetId(runConfig);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (runValidationIssues.length > 0) {
      setError("Resolve the highlighted run setup issues before verification.");
      return;
    }

    setIsSubmitting(true);

    try {
      const payload: ProofRunCreate = {
        claim,
        target_url: emptyToNull(targetUrl),
        api_base_url: emptyToNull(apiBaseUrl),
        repo_path: emptyToNull(repoPath),
        target_db_url: emptyToNull(targetDbUrl),
        run_config: runConfig,
      };
      const run = await createRun(payload);
      setRuns((currentRuns) => [run, ...currentRuns]);
      setSelectedRunId(run.id);
      setShowAllRuns(false);
    } catch {
      setError("ProofMode could not create a run.");
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleSeedDemo() {
    setIsSeedingDemo(true);
    setError(null);

    try {
      const demoRuns = await seedDemoRuns();
      const loadedRuns = await listRuns();
      setRuns(loadedRuns);
      setSelectedRunId(demoRuns[0]?.id ?? loadedRuns[0]?.id ?? null);
      setShowAllRuns(false);
    } catch {
      setError("ProofMode could not seed demo runs.");
    } finally {
      setIsSeedingDemo(false);
    }
  }

  async function handleSaveProject() {
    const trimmedName = projectName.trim();
    if (!trimmedName) {
      setError("Project name is required before saving.");
      return;
    }

    setIsSavingProject(true);
    setError(null);

    const payload = {
      name: trimmedName,
      target_url: emptyToNull(targetUrl),
      api_base_url: emptyToNull(apiBaseUrl),
      repo_path: emptyToNull(repoPath),
      target_db_url: emptyToNull(targetDbUrl),
      default_run_config: runConfig,
    };

    try {
      const savedProject = selectedProjectId
        ? await updateProject(selectedProjectId, payload)
        : await createProject(payload);
      setProjects((currentProjects) => upsertProject(currentProjects, savedProject));
      setSelectedProjectId(savedProject.id);
      setProjectName(savedProject.name);
    } catch {
      setError("ProofMode could not save this project profile.");
    } finally {
      setIsSavingProject(false);
    }
  }

  async function handleDuplicateProject() {
    const sourceName = projectName.trim() || selectedProject?.name || "ProofMode local";
    setIsSavingProject(true);
    setError(null);

    try {
      const duplicatedProject = await createProject({
        name: `${sourceName} copy`,
        target_url: emptyToNull(targetUrl),
        api_base_url: emptyToNull(apiBaseUrl),
        repo_path: emptyToNull(repoPath),
        target_db_url: emptyToNull(targetDbUrl),
        default_run_config: runConfig,
      });
      setProjects((currentProjects) => [duplicatedProject, ...currentProjects]);
      applyProject(duplicatedProject);
    } catch {
      setError("ProofMode could not duplicate this project profile.");
    } finally {
      setIsSavingProject(false);
    }
  }

  async function handleDeleteProject() {
    if (!selectedProjectId) {
      return;
    }

    setIsSavingProject(true);
    setError(null);

    try {
      await deleteProject(selectedProjectId);
      setProjects((currentProjects) => currentProjects.filter((project) => project.id !== selectedProjectId));
      resetProjectForm();
    } catch {
      setError("ProofMode could not delete this project profile.");
    } finally {
      setIsSavingProject(false);
    }
  }

  function handleProjectSelection(projectId: string) {
    setSelectedProjectId(projectId);

    if (!projectId) {
      return;
    }

    const selectedProject = projects.find((project) => project.id === projectId);
    if (selectedProject) {
      applyProject(selectedProject);
    }
  }

  function applyProject(project: ProjectProfile) {
    setSelectedProjectId(project.id);
    setProjectName(project.name);
    setTargetUrl(project.target_url ?? "");
    setApiBaseUrl(project.api_base_url ?? "");
    setRepoPath(project.repo_path ?? "");
    setTargetDbUrl(project.target_db_url ?? "");
    setRunConfig(project.default_run_config);
  }

  function resetProjectForm() {
    setSelectedProjectId("");
    setProjectName("ProofMode local");
    setTargetUrl("http://localhost:5173");
    setApiBaseUrl("http://localhost:8000/health");
    setRepoPath("");
    setTargetDbUrl("");
    setRunConfig(defaultRunConfig);
    setError(null);
  }

  function applyRunPreset(preset: RunPreset) {
    setRunConfig(preset.config);
    setError(null);
  }

  return (
    <main className="app-shell">
      <section className="topbar">
        <div className="brand-mark">
          <ShieldCheck size={24} />
        </div>
        <div className="brand-copy">
          <p className="eyebrow">Agent verification layer</p>
          <h1>ProofMode</h1>
        </div>
        <div className="run-metrics" aria-label="Run metrics">
          <Metric label="Passed" value={runCounts.passed} tone="passed" />
          <Metric label="Failed" value={runCounts.failed} tone="failed" />
          <Metric label="Uncertain" value={runCounts.uncertain} tone="uncertain" />
        </div>
      </section>

      <SettingsStatusPanel status={settingsStatus} />

      <section className="claim-panel">
        <div className="panel-heading">
          <div>
            <p className="eyebrow">Verification Console</p>
            <h2>New Proof Run</h2>
          </div>
          <button
            className="demo-seed-button"
            disabled={isSubmitting || isSeedingDemo}
            onClick={handleSeedDemo}
            type="button"
          >
            <Sparkles size={16} />
            {isSeedingDemo ? "Seeding" : "Seed Demo Runs"}
          </button>
        </div>
        <section className="project-profile-panel" aria-label="Project profile">
          <div className="project-profile-fields">
            <label>
              Project
              <select
                onChange={(event) => handleProjectSelection(event.target.value)}
                value={selectedProjectId}
              >
                <option value="">New project profile</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Project name
              <input
                onChange={(event) => setProjectName(event.target.value)}
                placeholder="ProofMode local"
                value={projectName}
              />
            </label>
          </div>
          <div className="project-profile-actions">
            <button
              className="secondary-icon-button"
              disabled={isSavingProject}
              onClick={resetProjectForm}
              title="Start a new project profile"
              type="button"
            >
              <Plus size={16} />
            </button>
            <button
              className="secondary-icon-button"
              disabled={isSavingProject || !selectedProject}
              onClick={handleDuplicateProject}
              title="Duplicate selected project profile"
              type="button"
            >
              <Copy size={16} />
            </button>
            <button
              className="secondary-icon-button secondary-icon-button--danger"
              disabled={isSavingProject || !selectedProject}
              onClick={handleDeleteProject}
              title="Delete selected project profile"
              type="button"
            >
              <Trash2 size={16} />
            </button>
            <button
              className="save-project-button"
              disabled={isSavingProject || projectName.trim().length === 0}
              onClick={handleSaveProject}
              type="button"
            >
              <Save size={16} />
              {isSavingProject ? "Saving" : selectedProjectId ? "Update Project" : "Save Project"}
            </button>
          </div>
        </section>
        <form onSubmit={handleSubmit}>
          <label htmlFor="claim">Task completion claim</label>
          <div className="claim-form-row claim-form-row--primary">
            <input
              id="claim"
              value={claim}
              onChange={(event) => setClaim(event.target.value)}
              placeholder="Describe what the agent claims is done"
            />
            <button disabled={isSubmitting || !canSubmitRun} type="submit">
              Verify
            </button>
          </div>
          <section className="run-config-panel" aria-label="Proof run configuration">
            <div className="run-config-copy">
              <p className="config-label">Proof checks</p>
              <p className="config-hint">Choose what ProofMode should execute for this run.</p>
            </div>
            <div className="run-preset-grid" aria-label="Run presets">
              {runPresets.map((preset) => (
                <button
                  className={`run-preset-button ${activePresetId === preset.id ? "run-preset-button--active" : ""}`}
                  key={preset.id}
                  onClick={() => applyRunPreset(preset)}
                  type="button"
                >
                  <strong>{preset.label}</strong>
                  <span>{preset.description}</span>
                </button>
              ))}
            </div>
            <div className="run-config-grid">
              <ConfigToggle
                checked={runConfig.ui_enabled}
                icon={<MonitorCheck size={17} />}
                label="UI"
                onChange={(checked) => setRunConfig((current) => ({ ...current, ui_enabled: checked }))}
              />
              <ConfigToggle
                checked={runConfig.api_enabled}
                icon={<Globe2 size={17} />}
                label="API"
                onChange={(checked) => setRunConfig((current) => ({ ...current, api_enabled: checked }))}
              />
              <ConfigToggle
                checked={runConfig.db_enabled}
                icon={<Database size={17} />}
                label="DB"
                onChange={(checked) => setRunConfig((current) => ({ ...current, db_enabled: checked }))}
              />
              <ConfigToggle
                checked={runConfig.diff_enabled}
                icon={<GitBranch size={17} />}
                label="Git diff"
                onChange={(checked) => setRunConfig((current) => ({ ...current, diff_enabled: checked }))}
              />
              <ConfigToggle
                checked={runConfig.planner_enabled}
                icon={<Sparkles size={17} />}
                label="Planner"
                onChange={(checked) => setRunConfig((current) => ({ ...current, planner_enabled: checked }))}
              />
              <ConfigToggle
                checked={runConfig.approval_required}
                icon={<ShieldCheck size={17} />}
                label="Approval"
                onChange={(checked) => setRunConfig((current) => ({ ...current, approval_required: checked }))}
              />
            </div>
          </section>
          <ValidationSummary issues={runValidationIssues} />
          <div className="advanced-fields">
            <label className={fieldNeedsAttention(runValidationIssues, "targetUrl") ? "field-warning" : ""}>
              Target URL
              <input
                onChange={(event) => setTargetUrl(event.target.value)}
                placeholder="http://localhost:5173"
                value={targetUrl}
              />
            </label>
            <label className={fieldNeedsAttention(runValidationIssues, "apiBaseUrl") ? "field-warning" : ""}>
              API URL
              <input
                onChange={(event) => setApiBaseUrl(event.target.value)}
                placeholder="http://localhost:8000/health"
                value={apiBaseUrl}
              />
            </label>
            <label className={fieldNeedsAttention(runValidationIssues, "repoPath") ? "field-warning" : ""}>
              Repo Path
              <input
                onChange={(event) => setRepoPath(event.target.value)}
                placeholder="C:\\path\\to\\repo"
                value={repoPath}
              />
            </label>
            <label className={fieldNeedsAttention(runValidationIssues, "targetDbUrl") ? "field-warning" : ""}>
              DB URL
              <input
                onChange={(event) => setTargetDbUrl(event.target.value)}
                placeholder="sqlite:///./proofmode-runs/demo.db"
                value={targetDbUrl}
              />
            </label>
          </div>
        </form>
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="workspace-grid">
        <section className="runs-section">
          <div className="section-heading runs-heading">
            <div>
              <p className="eyebrow">Reports</p>
              <h2>Verification Runs</h2>
            </div>
            <label className="run-search" htmlFor="run-search">
              <Search size={15} />
              <input
                id="run-search"
                onChange={(event) => {
                  setRunSearch(event.target.value);
                  setShowAllRuns(false);
                }}
                placeholder="Search runs"
                value={runSearch}
              />
            </label>
          </div>
          {runs.length === 0 ? (
            <div className="empty-state">No proof runs yet.</div>
          ) : filteredRuns.length === 0 ? (
            <div className="empty-state">No runs match your search.</div>
          ) : (
            <>
              <div className="runs-list">
                {visibleRuns.map((run) => (
                  <RunCard
                    isSelected={run.id === selectedRun?.id}
                    key={run.id}
                    onSelect={() => setSelectedRunId(run.id)}
                    run={run}
                  />
                ))}
              </div>
              <div className="runs-list-footer">
                <span>
                  Showing {visibleRuns.length} of {filteredRuns.length}
                  {runSearch.trim() ? " matching" : ""} run{filteredRuns.length === 1 ? "" : "s"}
                </span>
                {filteredRuns.length > 4 ? (
                  <button
                    className="show-more-button"
                    onClick={() => setShowAllRuns((current) => !current)}
                    type="button"
                  >
                    {showAllRuns ? "Show Less" : `Show ${hiddenRunCount} More`}
                  </button>
                ) : null}
              </div>
            </>
          )}
        </section>

        <RunDetail
          allRuns={runs}
          onRunUpdated={(updatedRun) => {
            setRuns((currentRuns) =>
              currentRuns.map((run) => (run.id === updatedRun.id ? updatedRun : run))
            );
            setSelectedRunId(updatedRun.id);
          }}
          run={selectedRun}
        />
      </section>
    </main>
  );
}

type RunValidationIssue = {
  field: "targetUrl" | "apiBaseUrl" | "repoPath" | "targetDbUrl" | "runConfig";
  layer: string;
  message: string;
};

type RunPreset = {
  id: string;
  label: string;
  description: string;
  config: RunConfiguration;
};

const defaultRunConfig: RunConfiguration = {
  ui_enabled: true,
  api_enabled: true,
  db_enabled: true,
  diff_enabled: true,
  planner_enabled: true,
  approval_required: true,
};

const runPresets: RunPreset[] = [
  {
    id: "full",
    label: "Full",
    description: "UI, API, DB, diff",
    config: defaultRunConfig,
  },
  {
    id: "ui",
    label: "UI only",
    description: "Browser proof",
    config: {
      ui_enabled: true,
      api_enabled: false,
      db_enabled: false,
      diff_enabled: false,
      planner_enabled: true,
      approval_required: true,
    },
  },
  {
    id: "backend",
    label: "Backend/API",
    description: "API plus diff",
    config: {
      ui_enabled: false,
      api_enabled: true,
      db_enabled: false,
      diff_enabled: true,
      planner_enabled: true,
      approval_required: true,
    },
  },
  {
    id: "migration",
    label: "DB migration",
    description: "DB plus diff",
    config: {
      ui_enabled: false,
      api_enabled: false,
      db_enabled: true,
      diff_enabled: true,
      planner_enabled: true,
      approval_required: true,
    },
  },
  {
    id: "diff",
    label: "Git diff",
    description: "Static review",
    config: {
      ui_enabled: false,
      api_enabled: false,
      db_enabled: false,
      diff_enabled: true,
      planner_enabled: true,
      approval_required: true,
    },
  },
];

function ValidationSummary({ issues }: { issues: RunValidationIssue[] }) {
  if (issues.length === 0) {
    return null;
  }

  return (
    <section className="validation-summary" aria-live="polite">
      <div>
        <AlertTriangle size={17} />
        <strong>Run setup needs attention</strong>
      </div>
      <ul>
        {issues.map((issue) => (
          <li key={`${issue.field}-${issue.layer}`}>{issue.message}</li>
        ))}
      </ul>
    </section>
  );
}

function ConfigToggle({
  checked,
  icon,
  label,
  onChange,
}: {
  checked: boolean;
  icon: ReactNode;
  label: string;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className={`config-toggle ${checked ? "config-toggle--checked" : ""}`}>
      <input
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        type="checkbox"
      />
      <span className="config-toggle__icon">{icon}</span>
      <span>{label}</span>
    </label>
  );
}

function SettingsStatusPanel({ status }: { status: SettingsStatus | null }) {
  const backendOnline = status?.backend_status === "online";

  return (
    <section className="settings-status-panel" aria-label="Environment status">
      <StatusChip
        icon={<Server size={15} />}
        label="Backend"
        tone={backendOnline ? "passed" : "failed"}
        value={backendOnline ? "Online" : "Unknown"}
      />
      <StatusChip
        icon={<Settings2 size={15} />}
        label="Planner"
        tone={status?.planner_mode === "llm" ? "passed" : "neutral"}
        value={status?.planner_mode ?? "unknown"}
      />
      <StatusChip
        icon={<ClipboardCheck size={15} />}
        label="Evaluator"
        tone={status?.evaluator_mode === "llm" ? "passed" : "neutral"}
        value={status?.evaluator_mode ?? "unknown"}
      />
      <StatusChip
        icon={<Sparkles size={15} />}
        label="Provider"
        tone={status?.llm_provider === "openai" ? "passed" : "neutral"}
        value={status?.llm_provider ?? "unknown"}
      />
      <StatusChip
        icon={<KeyRound size={15} />}
        label="API key"
        tone={status?.openai_api_key_configured ? "passed" : "uncertain"}
        value={status?.openai_api_key_configured ? "Configured" : "Missing"}
      />
      <StatusChip
        icon={<Database size={15} />}
        label="Runs"
        tone={status?.run_persistence_enabled ? "passed" : "failed"}
        value={status?.run_persistence_enabled ? "Persisted" : "Memory only"}
      />
    </section>
  );
}

function StatusChip({
  icon,
  label,
  tone,
  value,
}: {
  icon: ReactNode;
  label: string;
  tone: "passed" | "failed" | "neutral" | "uncertain";
  value: string;
}) {
  return (
    <div className={`settings-chip settings-chip--${tone}`}>
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function Metric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "passed" | "failed" | "uncertain";
}) {
  return (
    <div className={`metric metric--${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function getRunValidationIssues({
  apiBaseUrl,
  repoPath,
  runConfig,
  targetDbUrl,
  targetUrl,
}: {
  apiBaseUrl: string;
  repoPath: string;
  runConfig: RunConfiguration;
  targetDbUrl: string;
  targetUrl: string;
}): RunValidationIssue[] {
  const issues: RunValidationIssue[] = [];

  if (runConfig.ui_enabled && targetUrl.trim().length === 0) {
    issues.push({
      field: "targetUrl",
      layer: "UI",
      message: "UI verification is enabled, so add a target URL.",
    });
  }

  if (runConfig.api_enabled && apiBaseUrl.trim().length === 0) {
    issues.push({
      field: "apiBaseUrl",
      layer: "API",
      message: "API verification is enabled, so add an API URL.",
    });
  }

  if (runConfig.db_enabled && targetDbUrl.trim().length === 0) {
    issues.push({
      field: "targetDbUrl",
      layer: "DB",
      message: "Database verification is enabled, so add a DB URL.",
    });
  }

  if (runConfig.diff_enabled && repoPath.trim().length === 0) {
    issues.push({
      field: "repoPath",
      layer: "Git diff",
      message: "Git diff analysis is enabled, so add a repo path.",
    });
  }

  if (
    !runConfig.ui_enabled &&
    !runConfig.api_enabled &&
    !runConfig.db_enabled &&
    !runConfig.diff_enabled
  ) {
    issues.push({
      field: "runConfig",
      layer: "Proof checks",
      message: "Enable at least one automated proof check before running verification.",
    });
  }

  return issues;
}

function fieldNeedsAttention(issues: RunValidationIssue[], field: RunValidationIssue["field"]): boolean {
  return issues.some((issue) => issue.field === field);
}

function getActivePresetId(config: RunConfiguration): string | null {
  return runPresets.find((preset) => configsMatch(preset.config, config))?.id ?? null;
}

function configsMatch(first: RunConfiguration, second: RunConfiguration): boolean {
  return (
    first.ui_enabled === second.ui_enabled &&
    first.api_enabled === second.api_enabled &&
    first.db_enabled === second.db_enabled &&
    first.diff_enabled === second.diff_enabled &&
    first.planner_enabled === second.planner_enabled &&
    first.approval_required === second.approval_required
  );
}

function upsertProject(projects: ProjectProfile[], project: ProjectProfile): ProjectProfile[] {
  const existingIndex = projects.findIndex((currentProject) => currentProject.id === project.id);

  if (existingIndex === -1) {
    return [project, ...projects];
  }

  return projects.map((currentProject) => (currentProject.id === project.id ? project : currentProject));
}

function filterRuns(runs: ProofRun[], query: string): ProofRun[] {
  const normalizedQuery = query.trim().toLowerCase();

  if (!normalizedQuery) {
    return runs;
  }

  return runs.filter((run) => {
    const searchable = [
      run.claim,
      run.id,
      run.status,
      run.claim_source?.source,
      run.claim_source?.agent_name,
      run.claim_source?.external_id,
      run.approval?.decision,
      run.checklist.checks.map((check) => `${check.layer} ${check.type} ${check.description}`).join(" "),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchable.includes(normalizedQuery);
  });
}
