import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.schemas.runs import CheckStatus, ProofCheck, ProofRun
from app.services.artifacts import artifact_root


class ApiVerifier:
    layer = "api"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.api_base_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No API base URL was provided, so API contracts were not checked.",
            )

        snapshot_dir = artifact_root() / "snapshots" / "api"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = snapshot_dir / f"{self._snapshot_name(run.api_base_url)}.json"

        try:
            current_snapshot = self._capture_snapshot(run.api_base_url)
        except Exception as error:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="The API endpoint could not be reached for contract verification.",
                evidence={"api_base_url": run.api_base_url, "error": str(error)},
            )

        if not snapshot_path.exists():
            self._write_snapshot(snapshot_path, current_snapshot)
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="API baseline snapshot was created. Run verification again to detect contract drift.",
                evidence={
                    "api_base_url": run.api_base_url,
                    "snapshot_path": str(snapshot_path),
                    "status_code": current_snapshot["status_code"],
                },
            )

        previous_snapshot = self._read_snapshot(snapshot_path)
        issues = self._diff_snapshots(previous_snapshot, current_snapshot)
        self._write_snapshot(snapshot_path, current_snapshot)

        if issues:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="API contract drift was detected against the saved baseline.",
                evidence={
                    "api_base_url": run.api_base_url,
                    "snapshot_path": str(snapshot_path),
                    "issues": issues,
                    "status_code": current_snapshot["status_code"],
                },
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.PASSED,
            summary="API response matches the saved contract baseline.",
            evidence={
                "api_base_url": run.api_base_url,
                "snapshot_path": str(snapshot_path),
                "status_code": current_snapshot["status_code"],
            },
        )

    def _capture_snapshot(self, api_base_url: str) -> dict:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(api_base_url)
            content_type = response.headers.get("content-type", "")
            body = response.json() if "application/json" in content_type else response.text

        schema = self._extract_schema(body)
        return {
            "url": api_base_url,
            "status_code": response.status_code,
            "schema": schema,
            "schema_hash": hashlib.sha256(
                json.dumps(schema, sort_keys=True).encode("utf-8")
            ).hexdigest(),
        }

    def _extract_schema(self, value: object, depth: int = 0) -> object:
        if depth > 4:
            return "..."
        if isinstance(value, dict):
            return {key: self._extract_schema(item, depth + 1) for key, item in value.items()}
        if isinstance(value, list):
            return [self._extract_schema(value[0], depth + 1)] if value else []
        return type(value).__name__

    def _diff_snapshots(self, previous: dict, current: dict) -> list[dict[str, object]]:
        issues: list[dict[str, object]] = []

        if previous.get("status_code") != current.get("status_code"):
            issues.append(
                {
                    "type": "status_changed",
                    "before": previous.get("status_code"),
                    "after": current.get("status_code"),
                    "severity": "medium",
                }
            )

        missing_paths = self._missing_schema_paths(previous.get("schema"), current.get("schema"))
        for path in missing_paths:
            issues.append(
                {
                    "type": "field_removed",
                    "path": path,
                    "severity": "high",
                }
            )

        return issues

    def _missing_schema_paths(
        self, previous: object, current: object, prefix: str = ""
    ) -> list[str]:
        if isinstance(previous, dict):
            if not isinstance(current, dict):
                return [prefix or "$"]

            missing: list[str] = []
            for key, value in previous.items():
                path = f"{prefix}.{key}" if prefix else key
                if key not in current:
                    missing.append(path)
                else:
                    missing.extend(self._missing_schema_paths(value, current[key], path))
            return missing

        if isinstance(previous, list) and previous:
            if not isinstance(current, list) or not current:
                return [prefix or "$"]
            return self._missing_schema_paths(previous[0], current[0], f"{prefix}[]")

        if previous != current:
            return [prefix or "$"]

        return []

    def _read_snapshot(self, snapshot_path: Path) -> dict:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))

    def _write_snapshot(self, snapshot_path: Path, snapshot: dict) -> None:
        snapshot_path.write_text(
            json.dumps(snapshot, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _snapshot_name(self, api_base_url: str) -> str:
        parsed = urlparse(api_base_url)
        readable = f"{parsed.netloc}{parsed.path}".strip("/")
        readable = re.sub(r"[^A-Za-z0-9._-]+", "_", readable)
        digest = hashlib.sha256(api_base_url.encode("utf-8")).hexdigest()[:10]
        return f"{readable or 'api'}_{digest}"
