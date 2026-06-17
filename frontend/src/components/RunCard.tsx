import { AlertTriangle, CheckCircle2, CircleHelp, Database, GitBranch, Globe2, MonitorCheck } from "lucide-react";
import type { ProofRun, VerificationLayer } from "../types/runs";

const layerIcons: Record<VerificationLayer, typeof MonitorCheck> = {
  ui: MonitorCheck,
  api: Globe2,
  db: Database,
  diff: GitBranch,
};

export function RunCard({ run }: { run: ProofRun }) {
  const StatusIcon =
    run.status === "passed" ? CheckCircle2 : run.status === "failed" ? AlertTriangle : CircleHelp;

  return (
    <article className="run-card">
      <div className="run-card__header">
        <div>
          <p className="eyebrow">Proof Run</p>
          <h2>{run.claim}</h2>
        </div>
        <span className={`status-pill status-pill--${run.status}`}>
          <StatusIcon size={16} />
          {run.status}
        </span>
      </div>

      <div className="checks-grid">
        {run.checks.map((check) => {
          const LayerIcon = layerIcons[check.layer];
          return (
            <section className="check-row" key={check.layer}>
              <div className="check-row__icon" title={check.layer}>
                <LayerIcon size={18} />
              </div>
              <div>
                <p className="check-row__title">{check.layer.toUpperCase()}</p>
                <p>{check.summary}</p>
              </div>
            </section>
          );
        })}
      </div>
    </article>
  );
}

