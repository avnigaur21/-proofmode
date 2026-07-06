import json
import subprocess

from app.cli import main
from app.services.project_service import project_service


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
            "--json",
        ]
    )

    captured = capsys.readouterr()
    body = json.loads(captured.out)

    assert exit_code == 0
    assert body["status"] == "passed"
    assert body["evaluation"]["verdict"] == "supported"
    assert body["report_path"]


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


def _git(repo_path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_path, check=True, capture_output=True)
