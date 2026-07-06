from pathlib import Path

from app.schemas.runs import ProofRun
from app.services.artifacts import artifact_root, artifact_url


class ReportGenerator:
    def to_markdown(self, run: ProofRun) -> str:
        lines = [
            f"# ProofMode Report: {run.claim}",
            "",
            f"Status: `{run.status}`",
            "",
            "## Run Configuration",
            f"- UI verification: `{self._enabled(run.run_config.ui_enabled)}`",
            f"- API contract verification: `{self._enabled(run.run_config.api_enabled)}`",
            f"- Database state verification: `{self._enabled(run.run_config.db_enabled)}`",
            f"- Git diff analysis: `{self._enabled(run.run_config.diff_enabled)}`",
            f"- Verification planner: `{self._enabled(run.run_config.planner_enabled)}`",
            f"- Human approval gate: `{self._enabled(run.run_config.approval_required)}`",
            "",
            "## Claim Source",
            f"- Source: `{run.claim_source.source}`",
            f"- Agent: `{run.claim_source.agent_name or 'unspecified'}`",
            f"- Project ID: `{run.claim_source.project_id or 'none'}`",
            f"- External ID: `{run.claim_source.external_id or 'none'}`",
        ]

        if run.claim_source.metadata:
            lines.append("- Metadata:")
            lines.extend(
                f"  - `{key}`: `{value}`" for key, value in run.claim_source.metadata.items()
            )

        if run.approval:
            lines.extend(
                [
                    "",
                    f"Approval: `{run.approval.decision}`",
                    f"Reviewer: {run.approval.reviewer or 'Unspecified'}",
                ]
            )
            if run.approval.note:
                lines.append(f"Note: {run.approval.note}")

        if run.evaluation:
            lines.extend(
                [
                    "",
                    "## Evidence Evaluation",
                    f"- Verdict: `{run.evaluation.verdict}`",
                    f"- Confidence: `{run.evaluation.confidence:.2f}`",
                    f"- Explanation: {run.evaluation.explanation}",
                ]
            )
            if run.evaluation.reasons:
                lines.append("- Reasons:")
                lines.extend(f"  - {reason}" for reason in run.evaluation.reasons)
            if run.evaluation.rubrics:
                lines.append("- Rubrics:")
                lines.extend(
                    f"  - `{rubric.name}`: {rubric.score:.2f} ({rubric.label}) - {rubric.explanation}"
                    for rubric in run.evaluation.rubrics
                )
            if run.evaluation.guardrails:
                lines.append("- Guardrails:")
                lines.extend(f"  - {guardrail}" for guardrail in run.evaluation.guardrails)

        lines.extend(["", "## Planned Checklist"])

        for planned_check in run.checklist.checks:
            lines.append(
                f"- **{planned_check.layer}** `{planned_check.type}` - {planned_check.description}"
            )

        lines.extend(
            [
                "",
                "## Results",
            ]
        )

        for check in run.checks:
            lines.append(f"- **{check.layer}**: `{check.status}` - {check.summary}")

        if run.timeline:
            lines.extend(["", "## Agent Behavior Timeline"])
            for event in run.timeline:
                lines.append(
                    f"- `{event.timestamp.isoformat()}` **{event.layer}** `{event.status or 'info'}` - {event.message}"
                )

        diff_check = next((check for check in run.checks if check.layer == "diff"), None)
        if diff_check and diff_check.evidence.get("changed_files"):
            lines.extend(["", "## Changed Files"])
            for changed_file in diff_check.evidence["changed_files"]:
                categories = ", ".join(changed_file.get("categories", []))
                lines.append(f"- `{changed_file['path']}` -> {categories}")

            recommended = diff_check.evidence.get("recommended_layers", [])
            if recommended:
                lines.extend(["", "Recommended proof layers:"])
                lines.append(", ".join(f"`{layer}`" for layer in recommended))

        if run.checklist.affected_files_hint:
            lines.extend(["", "## Affected Files Hint"])
            for hint in run.checklist.affected_files_hint:
                lines.append(f"- `{hint}`")

        return "\n".join(lines)

    def _enabled(self, value: bool) -> str:
        return "enabled" if value else "disabled"

    def write_markdown(self, run: ProofRun) -> dict[str, str]:
        report_artifact = self.artifact_for(run)
        report_path = report_artifact["path"]
        Path(report_path).write_text(self.to_markdown(run), encoding="utf-8")
        return report_artifact

    def artifact_for(self, run: ProofRun) -> dict[str, str]:
        report_dir = artifact_root() / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_filename = f"{run.id}.md"
        report_path = report_dir / report_filename
        return {
            "path": str(report_path),
            "url": artifact_url("reports", report_filename),
        }
