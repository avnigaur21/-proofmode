import { ShieldCheck } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";
import { RunCard } from "../components/RunCard";
import { createRun, listRuns } from "../services/proofmodeApi";
import type { ProofRun } from "../types/runs";

export function App() {
  const [claim, setClaim] = useState("I added the first ProofMode verification loop");
  const [runs, setRuns] = useState<ProofRun[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns()
      .then(setRuns)
      .catch(() => setError("Backend is not reachable yet."));
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      const run = await createRun(claim);
      setRuns((currentRuns) => [run, ...currentRuns]);
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
          <div className="claim-form-row">
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
        </form>
        {error ? <p className="error-text">{error}</p> : null}
      </section>

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
              <RunCard key={run.id} run={run} />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

