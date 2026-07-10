import { AlertTriangle, Bot, CheckCircle2, CircleHelp, Database, GitBranch, Globe2, ListChecks, MonitorCheck } from "lucide-react";
import type { ProofRun, VerificationLayer } from "../types/runs";

const layerIcons: Record<VerificationLayer, typeof MonitorCheck> = {
  ui: MonitorCheck,
  api: Globe2,
  db: Database,
  diff: GitBranch,
  tests: ListChecks,
};

export function RunCard({
  run,
  isSelected,
  onSelect,
}: {
  run: ProofRun;
  isSelected: boolean;
  onSelect: () => void;
}) {
  const StatusIcon =
    run.status === "passed" ? CheckCircle2 : run.status === "failed" ? AlertTriangle : CircleHelp;

  return (
    <article className={`run-card ${isSelected ? "run-card--selected" : ""}`}>
      <div className="run-card__header">
        <div>
          <p className="eyebrow">Proof Run</p>
          <h2>{run.claim}</h2>
          <div className="claim-source-chip claim-source-chip--compact">
            <Bot size={13} />
            <span>{claimSourceLabel(run)}</span>
          </div>
        </div>
        <span className={`status-pill status-pill--${run.status}`}>
          <StatusIcon size={16} />
          {run.status}
        </span>
      </div>

      <section className="planned-checks">
        <p className="check-row__title">PLANNED CHECKLIST</p>
        <ul>
          {run.checklist.checks.slice(0, 4).map((check) => (
            <li key={`${check.layer}-${check.type}`}>
              <span>{check.layer.toUpperCase()}</span>
              {check.description}
            </li>
          ))}
        </ul>
      </section>

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
      <button className="secondary-button" type="button" onClick={onSelect}>
        Review Evidence
      </button>
    </article>
  );
}

function claimSourceLabel(run: ProofRun): string {
  const source = run.claim_source?.source ?? "manual";
  const agent = run.claim_source?.agent_name;
  return agent ? `${agent} via ${source}` : source;
}
