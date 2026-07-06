import json
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from app.schemas.runs import ProofRun
from app.services.artifacts import artifact_root, artifact_url


class EvidenceBundleService:
    def export(self, run: ProofRun) -> dict[str, str]:
        bundle_dir = artifact_root() / "bundles"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundle_dir / f"{run.id}-evidence-bundle.zip"

        files = self._bundle_files(run)
        manifest = self._manifest(run, files)

        with ZipFile(bundle_path, "w", compression=ZIP_DEFLATED) as bundle:
            bundle.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
            bundle.writestr("summary.md", self._summary_markdown(run))

            for archive_path, source_path in files:
                if source_path.is_file():
                    bundle.write(source_path, archive_path)

        return {
            "path": str(bundle_path),
            "url": artifact_url("bundles", bundle_path.name),
        }

    def _bundle_files(self, run: ProofRun) -> list[tuple[str, Path]]:
        files: list[tuple[str, Path]] = []
        root = artifact_root()

        self._add_if_exists(files, "run/run.json", root / "runs" / f"{run.id}.json")
        self._add_if_exists(files, "reports/report.md", Path(run.report_path) if run.report_path else None)

        for check in run.checks:
            evidence = check.evidence
            self._add_if_exists(
                files,
                f"screenshots/{check.layer}-{Path(str(evidence.get('screenshot_path'))).name}",
                self._path_from_evidence(evidence.get("screenshot_path")),
            )
            self._add_if_exists(
                files,
                f"evidence/{check.layer}-{Path(str(evidence.get('snapshot_path'))).name}",
                self._path_from_evidence(evidence.get("snapshot_path")),
            )
            self._add_if_exists(
                files,
                f"evidence/{check.layer}-{Path(str(evidence.get('evidence_path'))).name}",
                self._path_from_evidence(evidence.get("evidence_path")),
            )

        for claim_path in sorted((root / "claims").glob("*.json")):
            try:
                claim = json.loads(claim_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue

            if claim.get("run_id") == run.id:
                self._add_if_exists(files, f"claims/{claim_path.name}", claim_path)

        return files

    def _manifest(self, run: ProofRun, files: list[tuple[str, Path]]) -> dict[str, object]:
        return {
            "bundle_version": "1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": run.id,
            "claim": run.claim,
            "status": run.status,
            "evidence_verdict": run.evaluation.verdict if run.evaluation else None,
            "self_report_verdict": run.self_report_comparison.verdict if run.self_report_comparison else None,
            "approval_decision": run.approval.decision if run.approval else None,
            "claim_source": run.claim_source.model_dump(mode="json"),
            "files": [
                {
                    "path": archive_path,
                    "source": str(source_path),
                    "size_bytes": source_path.stat().st_size if source_path.is_file() else 0,
                }
                for archive_path, source_path in files
                if source_path.is_file()
            ],
        }

    def _summary_markdown(self, run: ProofRun) -> str:
        lines = [
            f"# ProofMode Evidence Bundle: {run.claim}",
            "",
            f"- Run ID: `{run.id}`",
            f"- Status: `{run.status}`",
            f"- Source: `{run.claim_source.source}`",
            f"- Agent: `{run.claim_source.agent_name or 'unspecified'}`",
        ]

        if run.agent_report:
            lines.extend(["", "## Agent Self-Report", run.agent_report])

        if run.evaluation:
            lines.extend(
                [
                    f"- Evidence verdict: `{run.evaluation.verdict}`",
                    f"- Confidence: `{run.evaluation.confidence:.2f}`",
                    f"- Evaluation: {run.evaluation.explanation}",
                ]
            )

        if run.self_report_comparison:
            lines.extend(
                [
                    "",
                    "## Agent Report vs Evidence",
                    f"- Verdict: `{run.self_report_comparison.verdict}`",
                    f"- Confidence: `{run.self_report_comparison.confidence:.2f}`",
                    f"- Summary: {run.self_report_comparison.summary}",
                ]
            )
            if run.self_report_comparison.mismatches:
                lines.append("- Mismatches:")
                lines.extend(
                    f"  - `{mismatch.topic}` `{mismatch.severity}`: {mismatch.explanation}"
                    for mismatch in run.self_report_comparison.mismatches
                )

        if run.approval:
            lines.extend(
                [
                    f"- Approval: `{run.approval.decision}`",
                    f"- Reviewer: `{run.approval.reviewer or 'unspecified'}`",
                ]
            )

        lines.extend(["", "## Checks"])
        for check in run.checks:
            lines.append(f"- **{check.layer.upper()}** `{check.status}` - {check.summary}")

        return "\n".join(lines) + "\n"

    def _add_if_exists(
        self,
        files: list[tuple[str, Path]],
        archive_path: str,
        source_path: Path | None,
    ) -> None:
        if source_path and source_path.is_file():
            files.append((archive_path, source_path))

    def _path_from_evidence(self, value: object) -> Path | None:
        return Path(str(value)) if isinstance(value, str) and value else None


evidence_bundle_service = EvidenceBundleService()
