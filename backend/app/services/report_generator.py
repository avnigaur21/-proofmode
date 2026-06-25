from pathlib import Path

from app.schemas.runs import ProofRun
from app.services.artifacts import artifact_root, artifact_url


class ReportGenerator:
    def to_markdown(self, run: ProofRun) -> str:
        lines = [
            f"# ProofMode Report: {run.claim}",
            "",
            f"Status: `{run.status}`",
        ]

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
