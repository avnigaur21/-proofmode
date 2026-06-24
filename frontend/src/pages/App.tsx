import { ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { RunCard } from "../components/RunCard";
import { RunDetail } from "../components/RunDetail";
import { createRun, listRuns } from "../services/proofmodeApi";
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

  return (
    <main className="app-shell">
      <section className="topbar">
        <div className="brand-mark">
          <ShieldCheck size={24} />
        </div>
        <div>
          <p className="eyebrow">Agent verification layer</p>
          <h1>ProofMode</h1>
        </div>
      </section>

      <section className="claim-panel">
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

        <RunDetail run={selectedRun} />
      </section>
    </main>
  );
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}
