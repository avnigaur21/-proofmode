import hashlib
import json
import re
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

from app.schemas.runs import CheckStatus, ProofCheck, ProofRun
from app.services.artifacts import artifact_root


class DbVerifier:
    layer = "db"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.target_db_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No database URL was provided, so database state was not checked.",
            )

        snapshot_dir = artifact_root() / "snapshots" / "db"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{self._snapshot_name(run.target_db_url)}.json"

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
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="Database baseline snapshot was created. Run verification again to detect state drift.",
                evidence={
                    "target_db_url": self._mask_db_url(run.target_db_url),
                    "snapshot_path": str(snapshot_path),
                    "tables_checked": len(current_snapshot["tables"]),
                },
            )

        previous_snapshot = self._read_snapshot(snapshot_path)
        issues = self._diff_snapshots(previous_snapshot, current_snapshot)
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
                    "tables_checked": len(current_snapshot["tables"]),
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
                    "tables_checked": len(current_snapshot["tables"]),
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
                "tables_checked": len(current_snapshot["tables"]),
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
