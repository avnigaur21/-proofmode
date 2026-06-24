import json
import subprocess
from pathlib import Path

from app.schemas.runs import CheckStatus, ProofCheck, ProofRun
from app.services.artifacts import artifact_root, artifact_url
from app.services.diff_analysis import (
    classify_changed_file,
    recommended_layers,
    summarize_categories,
)


class DiffVerifier:
    layer = "diff"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.repo_path is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No repository path was provided, so Git diff analysis was not checked.",
            )

        repo_path = Path(run.repo_path).expanduser().resolve()
        if not repo_path.exists():
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="The provided repository path does not exist.",
                evidence={"repo_path": str(repo_path)},
            )

        if not (repo_path / ".git").exists():
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="The provided repository path is not a Git repository.",
                evidence={"repo_path": str(repo_path)},
            )

        try:
            changed_files = self._changed_files(repo_path)
            diff_stats = self._diff_stats(repo_path)
        except Exception as error:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="Git diff analysis could not be completed.",
                evidence={"repo_path": str(repo_path), "error": str(error)},
            )

        category_summary = summarize_categories(changed_files)
        classified_files = [
            {"path": path, "categories": classify_changed_file(path)} for path in changed_files
        ]
        recommended = recommended_layers(category_summary)
        evidence_path = self._write_evidence(
            run.id,
            {
                "repo_path": str(repo_path),
                "changed_files": classified_files,
                "category_summary": category_summary,
                "recommended_layers": recommended,
                "diff_stats": diff_stats,
            },
        )
        evidence_url = self._evidence_url(run.id)

        if not changed_files:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.PASSED,
                summary="No uncommitted Git changes were detected.",
                evidence={
                    "repo_path": str(repo_path),
                    "changed_files": [],
                    "category_summary": category_summary,
                    "recommended_layers": recommended,
                    "evidence_path": str(evidence_path),
                    "evidence_url": evidence_url,
                },
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.PASSED,
            summary=f"Detected {len(changed_files)} changed file(s) and recommended proof layers.",
            evidence={
                "repo_path": str(repo_path),
                "changed_files": classified_files,
                "category_summary": category_summary,
                "recommended_layers": recommended,
                "diff_stats": diff_stats,
                "evidence_path": str(evidence_path),
                "evidence_url": evidence_url,
            },
        )

    def _changed_files(self, repo_path: Path) -> list[str]:
        names = set()

        for args in (
            ["diff", "--name-only"],
            ["diff", "--name-only", "--cached"],
            ["ls-files", "--others", "--exclude-standard"],
        ):
            output = self._git(repo_path, args)
            names.update(line.strip() for line in output.splitlines() if line.strip())

        return sorted(names)

    def _diff_stats(self, repo_path: Path) -> dict[str, object]:
        return {
            "unstaged": self._git(repo_path, ["diff", "--stat"]),
            "staged": self._git(repo_path, ["diff", "--cached", "--stat"]),
        }

    def _git(self, repo_path: Path, args: list[str]) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _write_evidence(self, run_id: str, evidence: dict) -> Path:
        diff_dir = artifact_root() / "snapshots" / "diff"
        diff_dir.mkdir(parents=True, exist_ok=True)
        evidence_filename = f"{run_id}.json"
        evidence_path = diff_dir / evidence_filename
        evidence_path.write_text(
            json.dumps(evidence, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return evidence_path

    def _evidence_url(self, run_id: str) -> str:
        return artifact_url("snapshots", "diff", f"{run_id}.json")
