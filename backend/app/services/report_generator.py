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

    def write_markdown(self, run: ProofRun) -> str:
        report_dir = artifact_root() / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / f"{run.id}.md"
        report_path.write_text(self.to_markdown(run), encoding="utf-8")
        return str(report_path)
