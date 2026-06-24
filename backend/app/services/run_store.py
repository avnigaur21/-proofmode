import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.runs import ProofRun
from app.services.artifacts import artifact_root, artifact_url


class RunStore:
    def __init__(self) -> None:
        self._runs_dir = artifact_root() / "runs"
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    def save(self, run: ProofRun) -> None:
        run_path = self._run_path(run.id)
        run_path.write_text(
            json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def load_all(self) -> dict[str, ProofRun]:
        runs: dict[str, ProofRun] = {}

        for run_path in sorted(self._runs_dir.glob("*.json")):
            try:
                run = ProofRun.model_validate_json(run_path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError):
                continue

            runs[run.id] = self._normalize_artifact_urls(run)

        return runs

    def _run_path(self, run_id: str) -> Path:
        return self._runs_dir / f"{run_id}.json"

    def _normalize_artifact_urls(self, run: ProofRun) -> ProofRun:
        if run.report_path and not run.report_url:
            report_name = Path(run.report_path).name
            run.report_url = artifact_url("reports", report_name)

        for check in run.checks:
            evidence = check.evidence

            if evidence.get("screenshot_path") and not evidence.get("screenshot_url"):
                evidence["screenshot_url"] = artifact_url(
                    "screenshots",
                    Path(str(evidence["screenshot_path"])).name,
                )

            if evidence.get("snapshot_path") and not evidence.get("snapshot_url"):
                snapshot_path = Path(str(evidence["snapshot_path"]))
                parent = snapshot_path.parent.name
                if parent in {"api", "db"}:
                    evidence["snapshot_url"] = artifact_url(
                        "snapshots",
                        parent,
                        snapshot_path.name,
                    )

            if evidence.get("evidence_path") and not evidence.get("evidence_url"):
                evidence["evidence_url"] = artifact_url(
                    "snapshots",
                    "diff",
                    Path(str(evidence["evidence_path"])).name,
                )

        return run

