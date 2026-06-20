from app.schemas.runs import ProofRun
from app.services.artifacts import artifact_root


class ReportGenerator:
    def to_markdown(self, run: ProofRun) -> str:
        lines = [
            f"# ProofMode Report: {run.claim}",
            "",
            f"Status: `{run.status}`",
            "",
            "## Planned Checklist",
        ]

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

        if run.checklist.affected_files_hint:
            lines.extend(["", "## Affected Files Hint"])
            for hint in run.checklist.affected_files_hint:
                lines.append(f"- `{hint}`")

        return "\n".join(lines)

    def write_markdown(self, run: ProofRun) -> str:
        report_dir = artifact_root() / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{run.id}.md"
        report_path.write_text(self.to_markdown(run), encoding="utf-8")
        return str(report_path)
