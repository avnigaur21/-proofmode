import argparse
import json
import os
import sys
from typing import Sequence

from pydantic import ValidationError

from app.schemas.claims import ClaimIngestionCreate
from app.schemas.projects import ProjectProfile
from app.schemas.runs import ProofRun, RunConfiguration
from app.services.claim_ingestion_service import claim_ingestion_service
from app.services.evidence_bundle import evidence_bundle_service
from app.services.project_service import project_service


CHECK_LAYERS = ("ui", "api", "db", "diff")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "verify":
        return _verify(args)

    parser.print_help()
    return 2


def _verify(args: argparse.Namespace) -> int:
    try:
        project = _resolve_project(args.project)
        run_config = _run_config_from_args(args, project)
        payload = ClaimIngestionCreate(
            claim=args.claim,
            agent_report=args.agent_report,
            source=args.source,
            agent_name=args.agent_name,
            project_id=project.id if project else None,
            external_id=args.external_id,
            metadata=_metadata_from_args(args),
            repo_path=args.repo_path,
            target_url=args.target_url,
            api_base_url=args.api_base_url,
            target_db_url=args.target_db_url,
            run_config=run_config,
            raw_payload={
                "argv": ["verify", *sys.argv[1:]] if args.capture_argv else [],
                "project": args.project,
                "checks": args.checks,
            },
        )
        result = claim_ingestion_service.ingest(payload)
    except (LookupError, ValueError, ValidationError) as exc:
        print(f"ProofMode CLI error: {exc}", file=sys.stderr)
        return 2

    run = result.run
    bundle_artifact = evidence_bundle_service.export(run) if args.bundle else None
    if bundle_artifact and args.bundle_path:
        _copy_bundle(bundle_artifact["path"], args.bundle_path)

    if args.json:
        print(
            json.dumps(
                {
                    "claim_id": result.claim_record.id,
                    "run_id": run.id,
                    "status": run.status,
                    "evaluation": run.evaluation.model_dump(mode="json") if run.evaluation else None,
                    "self_report_comparison": run.self_report_comparison.model_dump(mode="json")
                    if run.self_report_comparison
                    else None,
                    "checks": [check.model_dump(mode="json") for check in run.checks],
                    "report_path": run.report_path,
                    "report_url": run.report_url,
                    "bundle_path": bundle_artifact["path"] if bundle_artifact else None,
                    "bundle_url": bundle_artifact["url"] if bundle_artifact else None,
                },
                indent=2,
            )
        )
    else:
        _print_run_summary(result.claim_record.id, run)

    if args.summary_file:
        _write_summary_file(args.summary_file, result.claim_record.id, run)

    if args.github_step_summary:
        _append_github_step_summary(result.claim_record.id, run)

    if bundle_artifact and not args.json:
        print(f"Evidence bundle: {bundle_artifact['path']}")

    return 0 if str(run.status) == "passed" else 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="proofmode",
        description="Run ProofMode verification from terminal or CI.",
    )
    subparsers = parser.add_subparsers(dest="command")

    verify = subparsers.add_parser("verify", help="verify an agent completion claim")
    verify.add_argument("--claim", required=True, help="agent completion claim to verify")
    verify.add_argument("--agent-report", help="optional agent self-report to compare against evidence")
    verify.add_argument("--project", help="saved project id or exact project name")
    verify.add_argument("--source", default="cli", help="claim source label")
    verify.add_argument("--agent-name", help="agent/tool that produced the claim")
    verify.add_argument("--external-id", help="external commit, PR, job, or task id")
    verify.add_argument("--metadata", action="append", default=[], help="metadata as key=value; repeatable")
    verify.add_argument("--diff-base", help="base ref for PR/CI diff analysis, for example origin/main")
    verify.add_argument("--diff-head", help="head ref for PR/CI diff analysis, for example HEAD")
    verify.add_argument("--repo-path", help="repository path for Git diff verification")
    verify.add_argument("--target-url", help="target app URL for UI verification")
    verify.add_argument("--api-base-url", help="API URL for contract verification")
    verify.add_argument("--target-db-url", help="database URL for state verification")
    verify.add_argument(
        "--checks",
        help="comma-separated proof layers: full, ui, api, db, diff. Defaults to project config.",
    )
    verify.add_argument("--no-planner", action="store_true", help="disable checklist planner")
    verify.add_argument("--no-approval", action="store_true", help="mark human approval as not required")
    verify.add_argument("--json", action="store_true", help="print machine-readable JSON output")
    verify.add_argument("--summary-file", help="write a PR-friendly Markdown summary to this path")
    verify.add_argument("--bundle", action="store_true", help="export an evidence bundle ZIP for this run")
    verify.add_argument("--bundle-path", help="copy the generated evidence bundle ZIP to this path")
    verify.add_argument(
        "--github-step-summary",
        action="store_true",
        help="append the Markdown summary to GITHUB_STEP_SUMMARY when available",
    )
    verify.add_argument(
        "--capture-argv",
        action="store_true",
        help="store CLI argv in the claim raw payload for debugging",
    )

    return parser


def _resolve_project(project_ref: str | None) -> ProjectProfile | None:
    if not project_ref:
        return None

    projects = project_service.list_projects()
    for project in projects:
        if project.id == project_ref or project.name == project_ref:
            return project

    raise LookupError(f"Project not found: {project_ref}")


def _run_config_from_args(args: argparse.Namespace, project: ProjectProfile | None) -> RunConfiguration | None:
    if not args.checks and not args.no_planner and not args.no_approval:
        return None

    base_config = project.default_run_config if project and not args.checks else RunConfiguration()
    selected_layers = _selected_layers(args.checks) if args.checks else _layers_from_config(base_config)
    return base_config.model_copy(
        update={
            "ui_enabled": "ui" in selected_layers,
            "api_enabled": "api" in selected_layers,
            "db_enabled": "db" in selected_layers,
            "diff_enabled": "diff" in selected_layers,
            "planner_enabled": False if args.no_planner else base_config.planner_enabled,
            "approval_required": False if args.no_approval else base_config.approval_required,
        }
    )


def _selected_layers(raw_checks: str | None) -> set[str]:
    if not raw_checks:
        return set(CHECK_LAYERS)

    requested = {check.strip().lower() for check in raw_checks.split(",") if check.strip()}
    if "full" in requested:
        requested.remove("full")
        requested.update(CHECK_LAYERS)

    unknown = requested - set(CHECK_LAYERS)
    if unknown:
        raise ValueError(f"Unknown proof check layer(s): {', '.join(sorted(unknown))}")

    if not requested:
        raise ValueError("At least one proof check layer is required")

    return requested


def _layers_from_config(config: RunConfiguration) -> set[str]:
    return {layer for layer in CHECK_LAYERS if config.is_layer_enabled(layer)}


def _metadata_from_args(args: argparse.Namespace) -> dict[str, str]:
    metadata: dict[str, str] = {}

    for item in args.metadata:
        if "=" not in item:
            raise ValueError(f"Metadata must use key=value format: {item}")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError("Metadata key cannot be blank")
        metadata[key] = value.strip()

    if args.diff_base:
        metadata["diff_base"] = args.diff_base
    if args.diff_head:
        metadata["diff_head"] = args.diff_head

    return metadata


def _print_run_summary(claim_id: str, run) -> None:
    print("ProofMode verification complete")
    print(f"Claim record: {claim_id}")
    print(f"Run: {run.id}")
    print(f"Status: {run.status}")

    if run.evaluation:
        print(f"Evidence verdict: {run.evaluation.verdict}")
        print(f"Confidence: {round(run.evaluation.confidence * 100)}%")
        print(f"Why: {run.evaluation.explanation}")

    if run.report_path:
        print(f"Report: {run.report_path}")


def _write_summary_file(path: str, claim_id: str, run: ProofRun) -> None:
    with open(path, "w", encoding="utf-8") as summary_file:
        summary_file.write(_to_pr_markdown(claim_id, run))


def _copy_bundle(source: str, destination: str) -> None:
    with open(source, "rb") as source_file:
        with open(destination, "wb") as destination_file:
            destination_file.write(source_file.read())


def _append_github_step_summary(claim_id: str, run: ProofRun) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with open(summary_path, "a", encoding="utf-8") as summary_file:
        summary_file.write(_to_pr_markdown(claim_id, run))
        summary_file.write("\n")


def _to_pr_markdown(claim_id: str, run: ProofRun) -> str:
    lines = [
        "## ProofMode PR Verification",
        "",
        f"**Claim:** {run.claim}",
        f"**Status:** `{run.status}`",
        f"**Claim record:** `{claim_id}`",
        f"**Run:** `{run.id}`",
    ]

    if run.evaluation:
        lines.extend(
            [
                "",
                "### Evidence Verdict",
                f"- Verdict: `{run.evaluation.verdict}`",
                f"- Confidence: `{round(run.evaluation.confidence * 100)}%`",
                f"- Reason: {run.evaluation.explanation}",
            ]
        )

    if run.self_report_comparison:
        lines.extend(
            [
                "",
                "### Agent Report vs Evidence",
                f"- Verdict: `{run.self_report_comparison.verdict}`",
                f"- Confidence: `{round(run.self_report_comparison.confidence * 100)}%`",
                f"- Summary: {run.self_report_comparison.summary}",
            ]
        )
        for mismatch in run.self_report_comparison.mismatches:
            lines.append(f"- `{mismatch.topic}` `{mismatch.severity}` - {mismatch.explanation}")

    if run.checks:
        lines.extend(["", "### Proof Checks"])
        for check in run.checks:
            lines.append(f"- **{check.layer.upper()}** `{check.status}` - {check.summary}")

    if run.report_path:
        lines.extend(["", f"Full report artifact: `{run.report_path}`"])

    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
