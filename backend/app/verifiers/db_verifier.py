import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.schemas.runs import CheckStatus, PlannedCheck, ProofCheck, ProofRun
from app.services.artifacts import artifact_root, artifact_url


class DbVerifier:
    layer = "db"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.target_db_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No database URL was provided, so database state was not checked.",
            )

        targeted_checks = self._targeted_checks(run)
        snapshot_dir = artifact_root() / "snapshots" / "db"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_filename = f"{self._snapshot_name(run.target_db_url)}.json"
        snapshot_path = snapshot_dir / snapshot_filename
        snapshot_url = artifact_url("snapshots", "db", snapshot_filename)

        try:
            current_snapshot = self._capture_snapshot(run.target_db_url)
        except Exception as error:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="Database snapshot could not be captured.",
                evidence={
                    "target_db_url": self._mask_db_url(run.target_db_url),
                    "error": str(error),
                },
            )

        if not snapshot_path.exists():
            self._write_snapshot(snapshot_path, current_snapshot)
            if targeted_checks:
                target_results, target_issues = self._evaluate_targeted_checks(
                    targeted_checks,
                    current_snapshot,
                    previous_snapshot=None,
                )
                if target_issues:
                    return ProofCheck(
                        layer=self.layer,
                        status=CheckStatus.FAILED,
                        summary=f"Targeted database verification found {len(target_issues)} issue(s).",
                        evidence={
                            "target_db_url": self._mask_db_url(run.target_db_url),
                            "snapshot_path": str(snapshot_path),
                            "snapshot_url": snapshot_url,
                            "tables_checked": len(current_snapshot["tables"]),
                            "target_results": target_results,
                            "issues": target_issues,
                        },
                    )

            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="Database baseline snapshot was created. Run verification again to detect state drift.",
                evidence={
                    "target_db_url": self._mask_db_url(run.target_db_url),
                    "snapshot_path": str(snapshot_path),
                    "snapshot_url": snapshot_url,
                    "tables_checked": len(current_snapshot["tables"]),
                    "target_results": target_results if targeted_checks else [],
                },
            )

        previous_snapshot = self._read_snapshot(snapshot_path)
        issues = self._diff_snapshots(previous_snapshot, current_snapshot)
        target_results, target_issues = self._evaluate_targeted_checks(
            targeted_checks,
            current_snapshot,
            previous_snapshot=previous_snapshot,
        )
        issues.extend(target_issues)
        self._write_snapshot(snapshot_path, current_snapshot)

        breaking_issues = [issue for issue in issues if issue["severity"] in {"critical", "high"}]
        if breaking_issues:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="Database schema drift was detected against the saved baseline.",
                evidence={
                    "target_db_url": self._mask_db_url(run.target_db_url),
                    "snapshot_path": str(snapshot_path),
                    "snapshot_url": snapshot_url,
                    "tables_checked": len(current_snapshot["tables"]),
                    "target_results": target_results,
                    "issues": issues,
                },
            )

        if issues:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.PASSED,
                summary="Database snapshot completed with non-breaking state changes.",
                evidence={
                    "target_db_url": self._mask_db_url(run.target_db_url),
                    "snapshot_path": str(snapshot_path),
                    "snapshot_url": snapshot_url,
                    "tables_checked": len(current_snapshot["tables"]),
                    "target_results": target_results,
                    "issues": issues,
                },
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.PASSED,
            summary="Database state matches the saved baseline.",
            evidence={
                "target_db_url": self._mask_db_url(run.target_db_url),
                "snapshot_path": str(snapshot_path),
                "snapshot_url": snapshot_url,
                "tables_checked": len(current_snapshot["tables"]),
                "target_results": target_results,
                "issues": [],
            },
        )

    def _capture_snapshot(self, target_db_url: str) -> dict:
        engine = create_engine(target_db_url)
        inspector = inspect(engine)
        table_names = [
            table_name
            for table_name in inspector.get_table_names()
            if not table_name.startswith("sqlite_")
        ]

        tables = {}
        with engine.connect() as connection:
            preparer = engine.dialect.identifier_preparer

            for table_name in sorted(table_names):
                columns = {
                    column["name"]: {
                        "type": str(column["type"]),
                        "nullable": bool(column.get("nullable", True)),
                    }
                    for column in inspector.get_columns(table_name)
                }
                schema_hash = hashlib.sha256(
                    json.dumps(columns, sort_keys=True).encode("utf-8")
                ).hexdigest()
                quoted_table_name = preparer.quote(table_name)
                row_count = connection.execute(
                    text(f"SELECT COUNT(*) FROM {quoted_table_name}")
                ).scalar_one()

                tables[table_name] = {
                    "row_count": row_count,
                    "columns": columns,
                    "schema_hash": schema_hash,
                }

        engine.dispose()
        return {
            "database": self._mask_db_url(target_db_url),
            "tables": tables,
            "table_count": len(tables),
        }

    def _targeted_checks(self, run: ProofRun) -> list[PlannedCheck]:
        return [
            check
            for check in run.checklist.checks
            if check.layer == self.layer
            and (
                check.assertions.get("table")
                or check.assertions.get("column")
                or check.assertions.get("expected_row_delta") is not None
            )
        ]

    def _evaluate_targeted_checks(
        self,
        checks: list[PlannedCheck],
        current_snapshot: dict,
        *,
        previous_snapshot: dict | None,
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        results: list[dict[str, object]] = []
        issues: list[dict[str, object]] = []
        current_tables = current_snapshot.get("tables", {})
        previous_tables = previous_snapshot.get("tables", {}) if previous_snapshot else {}

        for check in checks:
            assertions = check.assertions
            table_name = str(assertions.get("table") or check.target or "")
            column_name = assertions.get("column")
            expected_row_delta = assertions.get("expected_row_delta")
            current_table = current_tables.get(table_name)
            previous_table = previous_tables.get(table_name)

            result: dict[str, object] = {
                "type": check.type,
                "table": table_name,
                "column": column_name,
                "expected_row_delta": expected_row_delta,
                "table_exists": current_table is not None,
            }

            if current_table is None:
                issues.append(
                    {
                        "type": "target_table_missing",
                        "table": table_name,
                        "severity": "high",
                    }
                )
                results.append(result)
                continue

            if isinstance(column_name, str) and column_name:
                column_exists = column_name in current_table.get("columns", {})
                result["column_exists"] = column_exists
                if not column_exists:
                    issues.append(
                        {
                            "type": "target_column_missing",
                            "table": table_name,
                            "column": column_name,
                            "severity": "high",
                        }
                    )

            if expected_row_delta is not None:
                if previous_table is None:
                    result["row_delta_status"] = "baseline_missing"
                    issues.append(
                        {
                            "type": "row_delta_baseline_missing",
                            "table": table_name,
                            "expected_delta": expected_row_delta,
                            "severity": "medium",
                        }
                    )
                else:
                    actual_delta = current_table["row_count"] - previous_table["row_count"]
                    result["actual_row_delta"] = actual_delta
                    if actual_delta != int(expected_row_delta):
                        issues.append(
                            {
                                "type": "target_row_delta_mismatch",
                                "table": table_name,
                                "expected_delta": expected_row_delta,
                                "actual_delta": actual_delta,
                                "severity": "high",
                            }
                        )

            results.append(result)

        return results, issues

    def _diff_snapshots(self, previous: dict, current: dict) -> list[dict[str, object]]:
        issues: list[dict[str, object]] = []
        previous_tables = previous.get("tables", {})
        current_tables = current.get("tables", {})

        for table_name, previous_table in previous_tables.items():
            current_table = current_tables.get(table_name)
            if current_table is None:
                issues.append(
                    {
                        "type": "table_removed",
                        "table": table_name,
                        "severity": "critical",
                    }
                )
                continue

            issues.extend(self._diff_columns(table_name, previous_table, current_table))

            row_delta = current_table["row_count"] - previous_table["row_count"]
            if row_delta != 0:
                issues.append(
                    {
                        "type": "row_count_changed",
                        "table": table_name,
                        "before": previous_table["row_count"],
                        "after": current_table["row_count"],
                        "delta": row_delta,
                        "severity": "info",
                    }
                )

        for table_name in current_tables:
            if table_name not in previous_tables:
                issues.append(
                    {
                        "type": "table_added",
                        "table": table_name,
                        "severity": "info",
                    }
                )

        return issues

    def _diff_columns(
        self, table_name: str, previous_table: dict, current_table: dict
    ) -> list[dict[str, object]]:
        issues: list[dict[str, object]] = []
        previous_columns = previous_table.get("columns", {})
        current_columns = current_table.get("columns", {})

        for column_name, previous_column in previous_columns.items():
            current_column = current_columns.get(column_name)
            if current_column is None:
                issues.append(
                    {
                        "type": "column_removed",
                        "table": table_name,
                        "column": column_name,
                        "severity": "high",
                    }
                )
                continue

            if previous_column["type"] != current_column["type"]:
                issues.append(
                    {
                        "type": "column_type_changed",
                        "table": table_name,
                        "column": column_name,
                        "before": previous_column["type"],
                        "after": current_column["type"],
                        "severity": "high",
                    }
                )

        for column_name in current_columns:
            if column_name not in previous_columns:
                issues.append(
                    {
                        "type": "column_added",
                        "table": table_name,
                        "column": column_name,
                        "severity": "info",
                    }
                )

        return issues

    def _read_snapshot(self, snapshot_path: Path) -> dict:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))

    def _write_snapshot(self, snapshot_path: Path, snapshot: dict) -> None:
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _snapshot_name(self, target_db_url: str) -> str:
        readable = re.sub(r"[^A-Za-z0-9._-]+", "_", self._mask_db_url(target_db_url))
        digest = hashlib.sha256(target_db_url.encode("utf-8")).hexdigest()[:10]
        return f"{readable.strip('_') or 'db'}_{digest}"

    def _mask_db_url(self, db_url: str) -> str:
        if "@" not in db_url:
            return db_url

        scheme, rest = db_url.split("://", 1) if "://" in db_url else ("", db_url)
        location = rest.split("@", 1)[1]
        return f"{scheme}://***@{location}" if scheme else f"***@{location}"
