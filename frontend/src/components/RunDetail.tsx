import {
  AlertTriangle,
  CheckCircle2,
  CircleHelp,
  ClipboardCheck,
  Database,
  FileText,
  GitBranch,
  Globe2,
  Image,
  MonitorCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { artifactUrl, loadTextArtifact } from "../services/proofmodeApi";
import type { ProofCheck, ProofRun, VerificationLayer } from "../types/runs";
import { MarkdownReport } from "./MarkdownReport";

const layerIcons: Record<VerificationLayer, typeof MonitorCheck> = {
  ui: MonitorCheck,
  api: Globe2,
  db: Database,
  diff: GitBranch,
};

export function RunDetail({ run }: { run: ProofRun | null }) {
  const [reportMarkdown, setReportMarkdown] = useState<string>("");
  const [reportError, setReportError] = useState<string | null>(null);

  useEffect(() => {
    setReportMarkdown("");
    setReportError(null);

    if (!run?.report_url) {
      return;
    }

    loadTextArtifact(run.report_url)
      .then(setReportMarkdown)
      .catch(() => setReportError("The report artifact is not available."));
  }, [run]);

  const checksByLayer = useMemo(() => {
    const grouped = new Map<VerificationLayer, ProofCheck>();
    run?.checks.forEach((check) => grouped.set(check.layer, check));
    return grouped;
  }, [run]);

  if (!run) {
    return (
      <section className="detail-panel detail-panel--empty">
        <ClipboardCheck size={34} />
        <h2>Select a run</h2>
        <p>Choose a verification run to inspect the claim, checklist, artifacts, and proof report.</p>
      </section>
    );
  }

  const StatusIcon =
    run.status === "passed" ? CheckCircle2 : run.status === "failed" ? AlertTriangle : CircleHelp;

  return (
    <section className="detail-panel">
      <div className="detail-header">
        <div>
          <p className="eyebrow">Run Detail</p>
          <h2>{run.claim}</h2>
        </div>
        <span className={`status-pill status-pill--${run.status}`}>
          <StatusIcon size={16} />
          {run.status}
        </span>
      </div>

      <section className="detail-section">
        <div className="section-title-row">
          <ClipboardCheck size={18} />
          <h3>Generated Checklist</h3>
        </div>
        <div className="checklist-table">
          {run.checklist.checks.map((check) => (
            <div className="checklist-item" key={`${check.layer}-${check.type}-${check.description}`}>
              <span>{check.layer.toUpperCase()}</span>
              <div>
                <strong>{check.type}</strong>
                <p>{check.description}</p>
              </div>
            </div>
          ))}
        </div>
      </section>

      <EvidenceSection check={checksByLayer.get("ui")} layer="ui" />
      <EvidenceSection check={checksByLayer.get("api")} layer="api" />
      <EvidenceSection check={checksByLayer.get("db")} layer="db" />
      <EvidenceSection check={checksByLayer.get("diff")} layer="diff" />

      <section className="detail-section">
        <div className="section-title-row">
          <FileText size={18} />
          <h3>Markdown Report</h3>
        </div>
        {reportError ? <p className="error-text">{reportError}</p> : null}
        {reportMarkdown ? (
          <MarkdownReport markdown={reportMarkdown} />
        ) : (
          <p className="muted-text">No report artifact loaded yet.</p>
        )}
      </section>
    </section>
  );
}

function EvidenceSection({ check, layer }: { check?: ProofCheck; layer: VerificationLayer }) {
  const Icon = layerIcons[layer];

  if (!check) {
    return null;
  }

  return (
    <section className="detail-section">
      <div className="section-title-row">
        <Icon size={18} />
        <h3>{layer.toUpperCase()} Evidence</h3>
        <span className={`mini-status mini-status--${check.status}`}>{check.status}</span>
      </div>
      <p className="evidence-summary">{check.summary}</p>
      {layer === "ui" ? <UiEvidence check={check} /> : null}
      {layer === "api" ? <IssueEvidence check={check} title="API Contract Issues" /> : null}
      {layer === "db" ? <IssueEvidence check={check} title="DB State Issues" /> : null}
      {layer === "diff" ? <DiffEvidence check={check} /> : null}
      <ArtifactLinks evidence={check.evidence} />
    </section>
  );
}

function UiEvidence({ check }: { check: ProofCheck }) {
  const screenshot = artifactUrl(asString(check.evidence.screenshot_url));
  const consoleErrors = asStringArray(check.evidence.console_errors);
  const pageErrors = asStringArray(check.evidence.page_errors);
  const networkFailures = asStringArray(check.evidence.network_failures);

  return (
    <>
      {screenshot ? (
        <figure className="screenshot-frame">
          <img src={screenshot} alt="Playwright verification screenshot" />
          <figcaption>
            <Image size={14} />
            Playwright screenshot
          </figcaption>
        </figure>
      ) : null}
      <EvidenceList title="Console errors" items={consoleErrors} />
      <EvidenceList title="Page errors" items={pageErrors} />
      <EvidenceList title="Network failures" items={networkFailures} />
    </>
  );
}

function IssueEvidence({ check, title }: { check: ProofCheck; title: string }) {
  const issues = asObjectArray(check.evidence.issues);

  return (
    <div className="issue-block">
      <h4>{title}</h4>
      {issues.length === 0 ? (
        <p className="muted-text">No issues reported.</p>
      ) : (
        <div className="issue-list">
          {issues.map((issue, index) => (
            <div className="issue-row" key={index}>
              <strong>{asString(issue.type) ?? "issue"}</strong>
              <code>{asString(issue.severity) ?? "info"}</code>
              <pre>{JSON.stringify(issue, null, 2)}</pre>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function DiffEvidence({ check }: { check: ProofCheck }) {
  const files = asObjectArray(check.evidence.changed_files);
  const recommended = asStringArray(check.evidence.recommended_layers);
  const visibleFiles = files.slice(0, 10);
  const hiddenFileCount = files.length - visibleFiles.length;

  return (
    <>
      {recommended.length > 0 ? (
        <div className="recommended-layers">
          {recommended.map((layer) => (
            <span key={layer}>{layer}</span>
          ))}
        </div>
      ) : null}
      {files.length === 0 ? (
        <p className="muted-text">No changed files reported.</p>
      ) : (
        <div className="changed-files">
          {visibleFiles.map((file, index) => (
            <div className="changed-file" key={index}>
              <code>{asString(file.path) ?? "unknown"}</code>
              <div className="file-category-list">
                {asStringArray(file.categories).map((category) => (
                  <span className="file-category" key={category}>
                    {category}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {hiddenFileCount > 0 ? (
            <div className="changed-file changed-file--more">
              {hiddenFileCount} more changed file{hiddenFileCount === 1 ? "" : "s"} in the artifact.
            </div>
          ) : null}
        </div>
      )}
    </>
  );
}

function ArtifactLinks({ evidence }: { evidence: Record<string, unknown> }) {
  const links = [
    ["Snapshot", asString(evidence.snapshot_url)],
    ["Diff Evidence", asString(evidence.evidence_url)],
  ].filter((entry): entry is [string, string] => Boolean(entry[1]));

  if (links.length === 0) {
    return null;
  }

  return (
    <div className="artifact-links">
      {links.map(([label, path]) => (
        <a href={artifactUrl(path) ?? "#"} key={path} rel="noreferrer" target="_blank">
          {label}
        </a>
      ))}
    </div>
  );
}

function EvidenceList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="evidence-list">
      <h4>{title}</h4>
      {items.length === 0 ? (
        <p className="muted-text">None captured.</p>
      ) : (
        <ul>
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

function asString(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function asObjectArray(value: unknown): Record<string, unknown>[] {
  return Array.isArray(value)
    ? value.filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    : [];
}
