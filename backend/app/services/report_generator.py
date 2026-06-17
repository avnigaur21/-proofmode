from app.schemas.runs import ProofRun


class ReportGenerator:
    def to_markdown(self, run: ProofRun) -> str:
        lines = [
            f"# ProofMode Report: {run.claim}",
            "",
            f"Status: `{run.status}`",
            "",
            "## Checks",
        ]

        for check in run.checks:
            lines.append(f"- **{check.layer}**: `{check.status}` - {check.summary}")

        return "\n".join(lines)

