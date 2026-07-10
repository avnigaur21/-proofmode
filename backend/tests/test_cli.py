import json
import subprocess
import tomllib
from pathlib import Path
from zipfile import ZipFile

from app.cli import main
from app.services.project_service import project_service


def test_package_exposes_proofmode_console_script() -> None:
    pyproject_path = Path(__file__).resolve().parents[1] / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    assert pyproject["project"]["name"] == "proofmode"
    assert pyproject["project"]["requires-python"] == ">=3.12"
    assert pyproject["project"]["scripts"]["proofmode"] == "app.cli:main"


def test_cli_verify_uses_project_profile_and_prints_summary(tmp_path, capsys) -> None:
    repo_path = _empty_repo(tmp_path)
    project = project_service.create_project(
        _project_payload(
            name="CLI demo app",
            repo_path=str(repo_path),
        )
    )

    exit_code = main(
        [
            "verify",
            "--claim",
            "Agent says login is complete",
            "--project",
            project.name,
            "--agent-name",
            "Codex",
            "--external-id",
            "commit-abc123",
            "--metadata",
            "branch=main",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ProofMode verification complete" in captured.out
    assert "Status: passed" in captured.out
    assert "Evidence verdict: supported" in captured.out


def test_cli_verify_supports_json_output_and_direct_config(tmp_path, capsys) -> None:
    repo_path = _empty_repo(tmp_path)

    exit_code = main(
        [
            "verify",
            "--claim",
            "Agent says checkout flow is complete",
            "--repo-path",
            str(repo_path),
            "--checks",
            "diff",
            "--source",
            "ci",
            "--agent-report",
            "I checked the Git diff and changed files.",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(captured.out)

    assert exit_code == 0
    assert body["status"] == "passed"
    assert body["evaluation"]["verdict"] == "supported"
    assert body["self_report_comparison"]["verdict"] == "aligned"
    assert body["checks"][0]["layer"] == "diff"
    assert body["report_path"]


def test_cli_verify_writes_pr_summary_and_uses_diff_range(tmp_path, capsys) -> None:
    repo_path = _repo_with_committed_change(tmp_path)
    summary_path = tmp_path / "proofmode-pr-summary.md"

    exit_code = main(
        [
            "verify",
            "--claim",
            "PR adds an auth route",
            "--repo-path",
            str(repo_path),
            "--checks",
            "diff",
            "--source",
            "github_pr",
            "--agent-report",
            "I ran tests and verified the API.",
            "--external-id",
            "pr-12",
            "--diff-base",
            "HEAD~1",
            "--diff-head",
            "HEAD",
            "--summary-file",
            str(summary_path),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(captured.out)
    summary = summary_path.read_text(encoding="utf-8")

    assert exit_code == 0
    assert body["checks"][0]["evidence"]["diff_range"] == "HEAD~1...HEAD"
    assert body["self_report_comparison"]["verdict"] == "partially_unsupported"
    assert body["checks"][0]["evidence"]["changed_files"][0]["path"] == "backend/app/routers/auth.py"
    assert "ProofMode PR Verification" in summary
    assert "**Status:** `passed`" in summary
    assert "**DIFF** `passed`" in summary


def test_cli_verify_exports_evidence_bundle(tmp_path, capsys) -> None:
    repo_path = _empty_repo(tmp_path)
    bundle_path = tmp_path / "proofmode-bundle.zip"

    exit_code = main(
        [
            "verify",
            "--claim",
            "Agent says settings page is complete",
            "--repo-path",
            str(repo_path),
            "--checks",
            "diff",
            "--bundle",
            "--bundle-path",
            str(bundle_path),
            "--json",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(captured.out)

    assert exit_code == 0
    assert body["bundle_path"]
    assert body["bundle_url"].startswith("/artifacts/bundles/")
    assert bundle_path.is_file()

    with ZipFile(bundle_path) as bundle:
        names = set(bundle.namelist())

    assert "manifest.json" in names
    assert "summary.md" in names
    assert "run/run.json" in names
    assert "reports/report.md" in names


def test_cli_verify_runs_test_command_evidence(tmp_path, capsys) -> None:
    exit_code = main(
        [
            "verify",
            "--claim",
            "Agent says tests pass",
            "--agent-report",
            "I ran the tests and they passed.",
            "--repo-path",
            str(tmp_path),
            "--checks",
            "tests",
            "--test-command",
            "Python smoke=python -c \"print('cli test evidence')\"",
            "--json",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(captured.out)

    assert exit_code == 0
    assert body["checks"][0]["layer"] == "tests"
    assert body["checks"][0]["evidence"]["commands"][0]["exit_code"] == 0
    assert body["self_report_comparison"]["verdict"] == "aligned"


def test_cli_verify_returns_usage_error_for_missing_project(capsys) -> None:
    exit_code = main(
        [
            "verify",
            "--claim",
            "Agent says auth works",
            "--project",
            "missing-cli-project",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 2
    assert "Project not found" in captured.err


def _project_payload(name: str, repo_path: str):
    from app.schemas.projects import ProjectProfileCreate
    from app.schemas.runs import RunConfiguration

    return ProjectProfileCreate(
        name=name,
        repo_path=repo_path,
        default_run_config=RunConfiguration(
            ui_enabled=False,
            api_enabled=False,
            db_enabled=False,
            diff_enabled=True,
            planner_enabled=True,
            approval_required=True,
        ),
    )


def _empty_repo(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    _git(repo_path, "init")
    _git(repo_path, "config", "user.name", "ProofMode Test")
    _git(repo_path, "config", "user.email", "proofmode@example.com")
    return repo_path


def _repo_with_committed_change(tmp_path):
    repo_path = _empty_repo(tmp_path)
    readme_path = repo_path / "README.md"
    readme_path.write_text("# Demo\n", encoding="utf-8")
    _git(repo_path, "add", "README.md")
    _git(repo_path, "commit", "-m", "Initial commit")

    auth_path = repo_path / "backend" / "app" / "routers" / "auth.py"
    auth_path.parent.mkdir(parents=True)
    auth_path.write_text("def login():\n    return {'ok': True}\n", encoding="utf-8")
    _git(repo_path, "add", "backend/app/routers/auth.py")
    _git(repo_path, "commit", "-m", "Add auth route")
    return repo_path


def _git(repo_path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)
