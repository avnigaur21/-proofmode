import { ShieldCheck, Sparkles } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { RunCard } from "../components/RunCard";
import { RunDetail } from "../components/RunDetail";
import { createRun, listRuns, seedDemoRuns } from "../services/proofmodeApi";
import type { ProofRun, ProofRunCreate } from "../types/runs";

export function App() {
  const [claim, setClaim] = useState("I added the first ProofMode verification loop");
  const [targetUrl, setTargetUrl] = useState("http://localhost:5173");
  const [apiBaseUrl, setApiBaseUrl] = useState("http://localhost:8000/health");
  const [repoPath, setRepoPath] = useState("");
  const [targetDbUrl, setTargetDbUrl] = useState("");
  const [runs, setRuns] = useState<ProofRun[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSeedingDemo, setIsSeedingDemo] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns()
      .then((loadedRuns) => {
        setRuns(loadedRuns);
        setSelectedRunId((current) => current ?? loadedRuns[0]?.id ?? null);
      })
      .catch(() => setError("Backend is not reachable yet."));
  }, []);

  const selectedRun = runs.find((run) => run.id === selectedRunId) ?? runs[0] ?? null;
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
      };
      const run = await createRun(payload);
      setRuns((currentRuns) => [run, ...currentRuns]);
      setSelectedRunId(run.id);
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
    } catch {
      setError("ProofMode could not seed demo runs.");
    } finally {
      setIsSeedingDemo(false);
    }
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
          <div className="section-heading">
            <p className="eyebrow">Reports</p>
            <h2>Verification Runs</h2>
          </div>
          {runs.length === 0 ? (
            <div className="empty-state">No proof runs yet.</div>
          ) : (
            <div className="runs-list">
              {runs.map((run) => (
                <RunCard
                  isSelected={run.id === selectedRun?.id}
                  key={run.id}
                  onSelect={() => setSelectedRunId(run.id)}
                  run={run}
                />
              ))}
            </div>
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
