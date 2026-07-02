import { Database, GitBranch, Globe2, KeyRound, MonitorCheck, Save, Search, Server, Settings2, ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { RunCard } from "../components/RunCard";
import { RunDetail } from "../components/RunDetail";
import {
  createProject,
  createRun,
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
  const filteredRuns = filterRuns(runs, runSearch);
  const visibleRuns = showAllRuns ? filteredRuns : filteredRuns.slice(0, 4);
  const hiddenRunCount = filteredRuns.length - visibleRuns.length;
  const runCounts = {
    passed: runs.filter((run) => run.status === "passed").length,
    failed: runs.filter((run) => run.status === "failed").length,
    uncertain: runs.filter((run) => run.status === "uncertain").length,
  };

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

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
          <button
            className="save-project-button"
            disabled={isSavingProject || projectName.trim().length === 0}
            onClick={handleSaveProject}
            type="button"
          >
            <Save size={16} />
            {isSavingProject ? "Saving" : selectedProjectId ? "Update Project" : "Save Project"}
          </button>
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
            <button disabled={isSubmitting || claim.trim().length === 0} type="submit">
              Verify
            </button>
          </div>
          <section className="run-config-panel" aria-label="Proof run configuration">
            <div>
              <p className="config-label">Proof checks</p>
              <p className="config-hint">Choose what ProofMode should execute for this run.</p>
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
          <div className="advanced-fields">
            <label>
              Target URL
              <input
                onChange={(event) => setTargetUrl(event.target.value)}
                placeholder="http://localhost:5173"
                value={targetUrl}
              />
            </label>
            <label>
              API URL
              <input
                onChange={(event) => setApiBaseUrl(event.target.value)}
                placeholder="http://localhost:8000/health"
                value={apiBaseUrl}
              />
            </label>
            <label>
              Repo Path
              <input
                onChange={(event) => setRepoPath(event.target.value)}
                placeholder="C:\\path\\to\\repo"
                value={repoPath}
              />
            </label>
            <label>
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

const defaultRunConfig: RunConfiguration = {
  ui_enabled: true,
  api_enabled: true,
  db_enabled: true,
  diff_enabled: true,
  planner_enabled: true,
  approval_required: true,
};

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
      run.approval?.decision,
      run.checklist.checks.map((check) => `${check.layer} ${check.type} ${check.description}`).join(" "),
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase();

    return searchable.includes(normalizedQuery);
  });
}
