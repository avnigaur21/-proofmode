import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  CircleHelp,
  ClipboardCheck,
  Clock3,
  Database,
  FileWarning,
  FileText,
  GitCompare,
  GitBranch,
  Globe2,
  Image,
  MonitorCheck,
  Sparkles,
  Wrench,
  XCircle,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { artifactUrl, loadTextArtifact, recordApproval } from "../services/proofmodeApi";
import type {
  ApprovalDecision,
  EvidenceEvaluation,
  ProofCheck,
  ProofRun,
  SelfReportComparison,
  TimelineEvent,
  VerificationLayer,
} from "../types/runs";
import { MarkdownReport } from "./MarkdownReport";

const layerIcons: Record<VerificationLayer, typeof MonitorCheck> = {
  ui: MonitorCheck,
  api: Globe2,
  db: Database,
  diff: GitBranch,
};

export function RunDetail({
  allRuns,
  onRunUpdated,
  run,
}: {
  allRuns: ProofRun[];
  onRunUpdated: (run: ProofRun) => void;
  run: ProofRun | null;
}) {
  const [reportMarkdown, setReportMarkdown] = useState<string>("");
  const [reportError, setReportError] = useState<string | null>(null);
  const [approvalNote, setApprovalNote] = useState("");
  const [reviewer, setReviewer] = useState("");
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [pendingDecision, setPendingDecision] = useState<ApprovalDecision | null>(null);

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
  const previousRun = useMemo(() => findPreviousRun(allRuns, run), [allRuns, run]);

  if (!run) {
    return (
      <section className="detail-panel detail-panel--empty">
        <ClipboardCheck size={34} />
        <h2>Select a run</h2>
        <p>Choose a verification run to inspect the claim, checklist, artifacts, and proof report.</p>
      </section>
    );
  }

  const currentRun = run;
  const StatusIcon =
    currentRun.status === "passed"
      ? CheckCircle2
      : currentRun.status === "failed"
        ? AlertTriangle
        : CircleHelp;

  async function handleApproval(decision: ApprovalDecision) {
    setPendingDecision(decision);
    setApprovalError(null);

    try {
      const updatedRun = await recordApproval(currentRun.id, {
        decision,
        note: emptyToNull(approvalNote),
        reviewer: emptyToNull(reviewer),
      });
      onRunUpdated(updatedRun);
      setApprovalNote("");
    } catch {
      setApprovalError("ProofMode could not save the approval decision.");
    } finally {
      setPendingDecision(null);
    }
  }

  return (
    <section className="detail-panel">
      <div className="detail-header">
        <div>
          <p className="eyebrow">Run Detail</p>
          <h2>{currentRun.claim}</h2>
        </div>
        <span className={`status-pill status-pill--${currentRun.status}`}>
          <StatusIcon size={16} />
          {currentRun.status}
        </span>
      </div>

      <RunConfigurationSummary run={currentRun} />

      <ClaimSourcePanel run={currentRun} />

      <SelfReportPanel comparison={currentRun.self_report_comparison} report={currentRun.agent_report} />

      <EvidenceEvaluationPanel evaluation={currentRun.evaluation} />

      <RunComparison currentRun={currentRun} previousRun={previousRun} />

      {currentRun.run_config.approval_required ? (
        <ApprovalGate
          error={approvalError}
          isPending={pendingDecision}
          note={approvalNote}
          onDecision={handleApproval}
          onNoteChange={setApprovalNote}
          onReviewerChange={setReviewer}
          reviewer={reviewer}
          run={currentRun}
        />
      ) : (
        <section className="approval-gate approval-gate--disabled">
          <div className="section-title-row">
            <ClipboardCheck size={18} />
            <h3>Approval Gate</h3>
            <span className="mini-status mini-status--uncertain">disabled</span>
          </div>
          <p className="muted-text">Human approval was not required for this proof run.</p>
        </section>
      )}

      <PlannerExplainability run={currentRun} />

      <section className="detail-section">
        <div className="section-title-row">
          <ClipboardCheck size={18} />
          <h3>Generated Checklist</h3>
          <span className={`planner-badge planner-badge--${plannerTone(currentRun.checklist.planner?.source)}`}>
            {plannerLabel(currentRun.checklist.planner)}
          </span>
        </div>
        <div className="checklist-table">
          {currentRun.checklist.checks.map((check) => (
            <div className="checklist-item" key={`${check.layer}-${check.type}-${check.description}`}>
              <span>{check.layer.toUpperCase()}</span>
              <div>
                <strong>{check.type}</strong>
                <p>{check.description}</p>
                <AssertionSummary assertions={check.assertions} />
              </div>
            </div>
          ))}
        </div>
      </section>

      <EvidenceSection check={checksByLayer.get("ui")} layer="ui" />
      <EvidenceSection check={checksByLayer.get("api")} layer="api" />
      <EvidenceSection check={checksByLayer.get("db")} layer="db" />
      <EvidenceSection check={checksByLayer.get("diff")} layer="diff" />

      <TimelineSection events={currentRun.timeline ?? []} />

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

function ClaimSourcePanel({ run }: { run: ProofRun }) {
  const source = run.claim_source ?? {
    source: "manual",
    agent_name: null,
    project_id: null,
    external_id: null,
    metadata: {},
  };
  const metadataEntries = Object.entries(source.metadata ?? {}).slice(0, 6);

  return (
    <section className="claim-source-panel">
      <div className="section-title-row">
        <Bot size={18} />
        <h3>Claim Intake</h3>
        <span className="mini-status mini-status--uncertain">{source.source}</span>
      </div>

      <div className="claim-source-grid">
        <ClaimSourceMetric label="Source" value={source.source} />
        <ClaimSourceMetric label="Agent" value={source.agent_name ?? "unspecified"} />
        <ClaimSourceMetric label="Project" value={source.project_id ?? "none"} />
        <ClaimSourceMetric label="External ID" value={source.external_id ?? "none"} />
      </div>

      {metadataEntries.length > 0 ? (
        <div className="claim-source-metadata">
          {metadataEntries.map(([key, value]) => (
            <code key={key}>
              {key}: {formatMetadataValue(value)}
            </code>
          ))}
        </div>
      ) : (
        <p className="muted-text">No extra source metadata was attached to this claim.</p>
      )}
    </section>
  );
}

function ClaimSourceMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="claim-source-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function SelfReportPanel({
  comparison,
  report,
}: {
  comparison?: SelfReportComparison | null;
  report?: string | null;
}) {
  if (!report && !comparison) {
    return (
      <section className="self-report-panel self-report-panel--empty">
        <div className="section-title-row">
          <FileWarning size={18} />
          <h3>Agent Report vs Evidence</h3>
        </div>
        <p className="muted-text">No agent self-report was attached to this run.</p>
      </section>
    );
  }

  return (
    <section className="self-report-panel">
      <div className="section-title-row">
        <FileWarning size={18} />
        <h3>Agent Report vs Evidence</h3>
        {comparison ? (
          <span className={`mini-status mini-status--${selfReportTone(comparison.verdict)}`}>
            {comparison.verdict.replace("_", " ")}
          </span>
        ) : null}
      </div>

      {report ? <blockquote className="agent-report-quote">{report}</blockquote> : null}

      {comparison ? (
        <>
          <div className="self-report-grid">
            <div className={`evaluation-score evaluation-score--${selfReportTone(comparison.verdict)}`}>
              <span>Confidence</span>
              <strong>{Math.round(comparison.confidence * 100)}%</strong>
            </div>
            <div className="evaluation-explanation">
              <span>comparison</span>
              <p>{comparison.summary}</p>
            </div>
          </div>

          {comparison.detected_claims.length > 0 ? (
            <div className="claim-source-metadata">
              {comparison.detected_claims.map((topic) => (
                <code key={topic}>{topic}</code>
              ))}
            </div>
          ) : null}

          {comparison.mismatches.length > 0 ? (
            <div className="self-report-mismatch-list">
              {comparison.mismatches.map((mismatch) => (
                <div className="self-report-mismatch" key={`${mismatch.topic}-${mismatch.explanation}`}>
                  <strong>{mismatch.topic}</strong>
                  <code>{mismatch.severity}</code>
                  <p>{mismatch.explanation}</p>
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function EvidenceEvaluationPanel({ evaluation }: { evaluation?: EvidenceEvaluation | null }) {
  if (!evaluation) {
    return (
      <section className="evaluation-panel evaluation-panel--empty">
        <div className="section-title-row">
          <ClipboardCheck size={18} />
          <h3>Evidence Evaluation</h3>
        </div>
        <p className="muted-text">No evidence evaluation has been recorded for this run.</p>
      </section>
    );
  }

  return (
    <section className="evaluation-panel">
      <div className="section-title-row">
        <ClipboardCheck size={18} />
        <h3>Evidence Evaluation</h3>
        <span className={`mini-status mini-status--${evaluationTone(evaluation.verdict)}`}>
          {evaluation.verdict}
        </span>
      </div>

      <div className="evaluation-grid">
        <div className={`evaluation-score evaluation-score--${evaluationTone(evaluation.verdict)}`}>
          <span>Confidence</span>
          <strong>{Math.round(evaluation.confidence * 100)}%</strong>
        </div>
        <div className="evaluation-explanation">
          <span>{evaluation.evaluator_mode}</span>
          <p>{evaluation.explanation}</p>
          <div className="evaluation-meta">
            <code>provider: {evaluation.provider ?? "local"}</code>
            <code>model: {evaluation.model ?? "n/a"}</code>
          </div>
        </div>
      </div>

      {evaluation.rubrics.length > 0 ? (
        <div className="rubric-grid">
          {evaluation.rubrics.map((rubric) => (
            <div className={`rubric-card rubric-card--${rubricTone(rubric.score)}`} key={rubric.name}>
              <div>
                <span>{formatRubricName(rubric.name)}</span>
                <strong>{Math.round(rubric.score * 100)}%</strong>
              </div>
              <code>{rubric.label}</code>
              <p>{rubric.explanation}</p>
            </div>
          ))}
        </div>
      ) : null}

      {evaluation.reasons.length > 0 ? (
        <EvidenceEvaluationList title="Reasons" items={evaluation.reasons} />
      ) : null}
      {evaluation.guardrails.length > 0 ? (
        <EvidenceEvaluationList title="Guardrails" items={evaluation.guardrails} />
      ) : null}
    </section>
  );
}

function EvidenceEvaluationList({ items, title }: { items: string[]; title: string }) {
  return (
    <div className="evaluation-list">
      <strong>{title}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function RunComparison({
  currentRun,
  previousRun,
}: {
  currentRun: ProofRun;
  previousRun: ProofRun | null;
}) {
  if (!previousRun) {
    return (
      <section className="comparison-panel comparison-panel--empty">
        <div className="section-title-row">
          <GitCompare size={18} />
          <h3>Run Comparison</h3>
        </div>
        <p className="muted-text">No earlier run is available for comparison yet.</p>
      </section>
    );
  }

  const rows = comparisonRows(currentRun, previousRun);

  return (
    <section className="comparison-panel">
      <div className="section-title-row">
        <GitCompare size={18} />
        <h3>Run Comparison</h3>
        <span className={`mini-status mini-status--${comparisonTone(currentRun, previousRun)}`}>
          {comparisonLabel(currentRun, previousRun)}
        </span>
      </div>

      <div className="comparison-grid">
        <ComparisonMetric label="Current verdict" tone={currentRun.status} value={currentRun.status} />
        <ComparisonMetric label="Previous verdict" tone={previousRun.status} value={previousRun.status} />
        <ComparisonMetric label="Checklist delta" tone="uncertain" value={checkDelta(currentRun, previousRun)} />
      </div>

      <div className="comparison-table" aria-label="Layer comparison">
        {rows.map((row) => (
          <div className="comparison-row" key={row.layer}>
            <span>{row.layer.toUpperCase()}</span>
            <strong className={`comparison-status comparison-status--${row.currentTone}`}>
              {row.current}
            </strong>
            <code>{row.previous}</code>
          </div>
        ))}
      </div>
    </section>
  );
}

function ComparisonMetric({
  label,
  tone,
  value,
}: {
  label: string;
  tone: string;
  value: string;
}) {
  return (
    <div className={`comparison-metric comparison-metric--${statusTone(tone)}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function AssertionSummary({ assertions }: { assertions?: Record<string, unknown> }) {
  if (!assertions || Object.keys(assertions).length === 0) {
    return null;
  }

  const visibleAssertions = Object.entries(assertions)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .slice(0, 4);

  if (visibleAssertions.length === 0) {
    return null;
  }

  return (
    <div className="assertion-summary">
      {visibleAssertions.map(([key, value]) => (
        <code key={key}>
          {key}: {formatAssertionValue(value)}
        </code>
      ))}
    </div>
  );
}

function PlannerExplainability({ run }: { run: ProofRun }) {
  const planner = run.checklist.planner;
  const plannerTimeline = run.timeline.find(
    (event) =>
      event.type === "planner.llm_completed" ||
      event.type === "planner.fallback_used" ||
      event.type === "planner.completed"
  );
  const influencedFiles = run.checklist.affected_files_hint.slice(0, 6);

  return (
    <section className="planner-panel">
      <div className="section-title-row">
        <Sparkles size={18} />
        <h3>Planner Explainability</h3>
        <span className={`planner-badge planner-badge--${plannerTone(planner?.source)}`}>
          {plannerLabel(planner)}
        </span>
      </div>

      <div className="planner-grid">
        <PlannerMetric label="Mode" value={planner?.mode ?? "deterministic"} />
        <PlannerMetric label="Provider" value={planner?.provider ?? "local"} />
        <PlannerMetric label="Model" value={planner?.model ?? "n/a"} />
        <PlannerMetric label="Diff files read" value={String(planner?.diff_files_used ?? 0)} />
        <PlannerMetric label="Diff truncated" value={planner?.diff_truncated ? "Yes" : "No"} />
        <PlannerMetric label="Fallback" value={planner?.used_fallback ? "Yes" : "No"} />
      </div>

      {planner?.used_fallback ? (
        <div className="planner-note planner-note--fallback">
          <strong>Fallback used</strong>
          <p>{planner.reason ? fallbackReason(planner.reason) : "The LLM planner could not produce a valid checklist."}</p>
        </div>
      ) : null}

      {plannerTimeline ? (
        <div className="planner-note">
          <strong>{plannerTimeline.type}</strong>
          <p>{plannerTimeline.message}</p>
        </div>
      ) : null}

      {influencedFiles.length > 0 ? (
        <div className="planner-files">
          {influencedFiles.map((file) => (
            <code key={file}>{file}</code>
          ))}
        </div>
      ) : (
        <p className="muted-text">No specific influenced files were recorded for this checklist.</p>
      )}
    </section>
  );
}

function RunConfigurationSummary({ run }: { run: ProofRun }) {
  const config = run.run_config;
  const items: Array<[string, boolean]> = [
    ["UI", config.ui_enabled],
    ["API", config.api_enabled],
    ["DB", config.db_enabled],
    ["Git diff", config.diff_enabled],
    ["Planner", config.planner_enabled],
    ["Approval", config.approval_required],
  ];

  return (
    <section className="run-config-summary" aria-label="Run configuration summary">
      {items.map(([label, enabled]) => (
        <span className={enabled ? "config-chip config-chip--enabled" : "config-chip"} key={label}>
          {label}
          <strong>{enabled ? "on" : "off"}</strong>
        </span>
      ))}
    </section>
  );
}

function PlannerMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="planner-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function ApprovalGate({
  error,
  isPending,
  note,
  onDecision,
  onNoteChange,
  onReviewerChange,
  reviewer,
  run,
}: {
  error: string | null;
  isPending: ApprovalDecision | null;
  note: string;
  onDecision: (decision: ApprovalDecision) => void;
  onNoteChange: (value: string) => void;
  onReviewerChange: (value: string) => void;
  reviewer: string;
  run: ProofRun;
}) {
  return (
    <section className="approval-gate">
      <div className="section-title-row">
        <ClipboardCheck size={18} />
        <h3>Approval Gate</h3>
        {run.approval ? (
          <span className={`mini-status mini-status--${approvalTone(run.approval.decision)}`}>
            {run.approval.decision.replace("_", " ")}
          </span>
        ) : null}
      </div>

      {run.approval ? (
        <div className="approval-record">
          <strong>{approvalLabel(run.approval.decision)}</strong>
          <p>
            {run.approval.reviewer || "Reviewer"} decided at {formatDateTime(run.approval.decided_at)}
          </p>
          {run.approval.note ? <blockquote>{run.approval.note}</blockquote> : null}
        </div>
      ) : (
        <p className="muted-text">No human decision has been recorded for this proof yet.</p>
      )}

      <div className="approval-fields">
        <label>
          Reviewer
          <input
            onChange={(event) => onReviewerChange(event.target.value)}
            placeholder="Your name"
            value={reviewer}
          />
        </label>
        <label>
          Decision note
          <input
            onChange={(event) => onNoteChange(event.target.value)}
            placeholder="Reason, fix instruction, or approval context"
            value={note}
          />
        </label>
      </div>

      <div className="approval-actions">
        <button
          className="approval-button approval-button--approve"
          disabled={Boolean(isPending)}
          onClick={() => onDecision("approved")}
          type="button"
        >
          <CheckCircle2 size={16} />
          {isPending === "approved" ? "Saving" : "Approve"}
        </button>
        <button
          className="approval-button approval-button--fix"
          disabled={Boolean(isPending)}
          onClick={() => onDecision("fix_requested")}
          type="button"
        >
          <Wrench size={16} />
          {isPending === "fix_requested" ? "Saving" : "Request Fix"}
        </button>
        <button
          className="approval-button approval-button--reject"
          disabled={Boolean(isPending)}
          onClick={() => onDecision("rejected")}
          type="button"
        >
          <XCircle size={16} />
          {isPending === "rejected" ? "Saving" : "Reject"}
        </button>
      </div>
      {error ? <p className="error-text">{error}</p> : null}
    </section>
  );
}

function TimelineSection({ events }: { events: TimelineEvent[] }) {
  return (
    <section className="detail-section">
      <div className="section-title-row">
        <Clock3 size={18} />
        <h3>Agent Behavior Timeline</h3>
      </div>
      {events.length === 0 ? (
        <p className="muted-text">No timeline events captured for this run.</p>
      ) : (
        <div className="timeline-list">
          {events.map((event, index) => (
            <div className="timeline-item" key={`${event.timestamp}-${event.type}-${index}`}>
              <div className={`timeline-dot timeline-dot--${statusTone(event.status)}`} />
              <div className="timeline-card">
                <div className="timeline-meta">
                  <time>{formatTime(event.timestamp)}</time>
                  <span>{event.layer}</span>
                  {event.status ? <code>{event.status}</code> : null}
                </div>
                <strong>{event.type}</strong>
                <p>{event.message}</p>
              </div>
            </div>
          ))}
        </div>
      )}
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

function formatTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function statusTone(status?: string | null): "passed" | "failed" | "uncertain" | "info" {
  if (status === "passed" || status === "completed" || status === "approved") {
    return "passed";
  }

  if (status === "failed" || status === "rejected") {
    return "failed";
  }

  if (status === "uncertain" || status === "running" || status === "pending" || status === "fix_requested") {
    return "uncertain";
  }

  return "info";
}

function approvalTone(decision: ApprovalDecision): "passed" | "failed" | "uncertain" {
  if (decision === "approved") {
    return "passed";
  }

  if (decision === "rejected") {
    return "failed";
  }

  return "uncertain";
}

function evaluationTone(verdict: string): "passed" | "failed" | "uncertain" {
  if (verdict === "supported") {
    return "passed";
  }

  if (verdict === "contradicted") {
    return "failed";
  }

  return "uncertain";
}

function selfReportTone(verdict: string): "passed" | "failed" | "uncertain" {
  if (verdict === "aligned") {
    return "passed";
  }

  if (verdict === "contradicted") {
    return "failed";
  }

  return "uncertain";
}

function rubricTone(score: number): "passed" | "failed" | "uncertain" {
  if (score >= 0.65) {
    return "passed";
  }

  if (score < 0.35) {
    return "failed";
  }

  return "uncertain";
}

function formatRubricName(name: string): string {
  return name
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function approvalLabel(decision: ApprovalDecision): string {
  if (decision === "approved") {
    return "Proof approved";
  }

  if (decision === "rejected") {
    return "Proof rejected";
  }

  return "Fix requested";
}

function emptyToNull(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function formatDateTime(value: string): string {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleString([], {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function plannerLabel(planner?: ProofRun["checklist"]["planner"]): string {
  if (!planner) {
    return "Planner: deterministic";
  }

  if (planner.source === "disabled") {
    return "Planner: disabled";
  }

  if (planner.used_fallback) {
    return "Planner: fallback";
  }

  if (planner.source === "llm") {
    return `Planner: LLM${planner.provider ? ` (${planner.provider})` : ""}`;
  }

  return "Planner: deterministic";
}

function plannerTone(source?: string): "deterministic" | "fallback" | "llm" {
  if (source === "llm") {
    return "llm";
  }

  if (source?.includes("fallback")) {
    return "fallback";
  }

  return "deterministic";
}

function fallbackReason(reason: string): string {
  const reasons: Record<string, string> = {
    llm_output_invalid: "The LLM response did not match ProofMode's checklist schema.",
    llm_provider_error: "The configured LLM provider was unavailable or returned an error.",
    llm_returned_no_checks: "The LLM returned no usable verification checks.",
    llm_planner_failed: "The LLM planner failed, so ProofMode used deterministic checks.",
  };

  return reasons[reason] ?? reason;
}

function findPreviousRun(allRuns: ProofRun[], currentRun: ProofRun | null): ProofRun | null {
  if (!currentRun) {
    return null;
  }

  const sortedRuns = [...allRuns].sort(
    (first, second) => new Date(second.created_at).getTime() - new Date(first.created_at).getTime()
  );
  const currentIndex = sortedRuns.findIndex((run) => run.id === currentRun.id);

  if (currentIndex === -1) {
    return null;
  }

  return sortedRuns[currentIndex + 1] ?? null;
}

function comparisonRows(currentRun: ProofRun, previousRun: ProofRun) {
  const layers: VerificationLayer[] = ["ui", "api", "db", "diff"];
  const currentChecks = checksByLayerMap(currentRun);
  const previousChecks = checksByLayerMap(previousRun);

  return layers.map((layer) => {
    const current = currentChecks.get(layer)?.status ?? "skipped";
    const previous = previousChecks.get(layer)?.status ?? "skipped";

    return {
      current,
      currentTone: current === "skipped" ? "uncertain" : current,
      layer,
      previous,
    };
  });
}

function checksByLayerMap(run: ProofRun): Map<VerificationLayer, ProofCheck> {
  const checks = new Map<VerificationLayer, ProofCheck>();
  run.checks.forEach((check) => checks.set(check.layer, check));
  return checks;
}

function checkDelta(currentRun: ProofRun, previousRun: ProofRun): string {
  const delta = currentRun.checklist.checks.length - previousRun.checklist.checks.length;

  if (delta > 0) {
    return `+${delta}`;
  }

  return String(delta);
}

function comparisonLabel(currentRun: ProofRun, previousRun: ProofRun): string {
  const currentScore = verdictScore(currentRun.status);
  const previousScore = verdictScore(previousRun.status);

  if (currentScore > previousScore) {
    return "improved";
  }

  if (currentScore < previousScore) {
    return "regressed";
  }

  return "unchanged";
}

function comparisonTone(currentRun: ProofRun, previousRun: ProofRun): "passed" | "failed" | "uncertain" {
  const label = comparisonLabel(currentRun, previousRun);

  if (label === "improved") {
    return "passed";
  }

  if (label === "regressed") {
    return "failed";
  }

  return "uncertain";
}

function verdictScore(status: string): number {
  if (status === "passed") {
    return 2;
  }

  if (status === "uncertain" || status === "pending" || status === "running") {
    return 1;
  }

  return 0;
}

function formatAssertionValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.join(", ");
  }

  if (typeof value === "object" && value !== null) {
    return JSON.stringify(value);
  }

  return String(value);
}

function formatMetadataValue(value: unknown): string {
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  return JSON.stringify(value);
}
