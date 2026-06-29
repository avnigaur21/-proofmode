import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import urljoin

import httpx

from app.schemas.runs import CheckStatus, PlannedCheck, ProofCheck, ProofRun
from app.services.artifacts import artifact_root, artifact_url


class ApiVerifier:
    layer = "api"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.api_base_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No API base URL was provided, so API contracts were not checked.",
            )

        targeted_checks = self._targeted_checks(run)
        if targeted_checks:
            return self._verify_targets(run, targeted_checks)

        snapshot_dir = artifact_root() / "snapshots" / "api"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_filename = f"{self._snapshot_name(run.api_base_url)}.json"
        snapshot_path = snapshot_dir / snapshot_filename
        snapshot_url = artifact_url("snapshots", "api", snapshot_filename)

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
                    "snapshot_url": snapshot_url,
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
                    "snapshot_url": snapshot_url,
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
                "snapshot_url": snapshot_url,
                "status_code": current_snapshot["status_code"],
            },
        )

    def _verify_targets(self, run: ProofRun, checks: list[PlannedCheck]) -> ProofCheck:
        assert run.api_base_url is not None
        results: list[dict[str, object]] = []
        issues: list[dict[str, object]] = []

        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            for check in checks:
                assertions = check.assertions
                method = str(assertions.get("method", "GET")).upper()
                path = str(assertions.get("path") or check.target or "")
                url = self._target_url(run.api_base_url, path)
                expected_status = int(assertions.get("expected_status", 200))
                required_fields = [
                    str(field) for field in assertions.get("required_fields", []) if field
                ]

                try:
                    response = client.request(method, url)
                    body = response.json() if "application/json" in response.headers.get("content-type", "") else None
                except Exception as error:
                    issues.append(
                        {
                            "type": "target_request_failed",
                            "target": url,
                            "method": method,
                            "error": str(error),
                            "severity": "high",
                        }
                    )
                    continue

                target_result = {
                    "type": check.type,
                    "method": method,
                    "url": url,
                    "status_code": response.status_code,
                    "expected_status": expected_status,
                    "required_fields": required_fields,
                }
                results.append(target_result)

                if response.status_code != expected_status:
                    issues.append(
                        {
                            "type": "target_status_mismatch",
                            "target": url,
                            "method": method,
                            "expected": expected_status,
                            "actual": response.status_code,
                            "severity": "high",
                        }
                    )

                if required_fields:
                    missing_fields = self._missing_required_fields(body, required_fields)
                    for field in missing_fields:
                        issues.append(
                            {
                                "type": "required_field_missing",
                                "target": url,
                                "field": field,
                                "severity": "high",
                            }
                        )

        if issues:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary=f"Targeted API verification found {len(issues)} issue(s).",
                evidence={"api_base_url": run.api_base_url, "target_results": results, "issues": issues},
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.PASSED,
            summary=f"Targeted API verification passed for {len(results)} endpoint check(s).",
            evidence={"api_base_url": run.api_base_url, "target_results": results, "issues": []},
        )

    def _targeted_checks(self, run: ProofRun) -> list[PlannedCheck]:
        return [
            check
            for check in run.checklist.checks
            if check.layer == self.layer
            and (
                check.assertions.get("path")
                or check.assertions.get("expected_status")
                or check.assertions.get("required_fields")
            )
        ]

    def _target_url(self, api_base_url: str, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path:
            return api_base_url
        return urljoin(api_base_url.rstrip("/") + "/", path.lstrip("/"))

    def _missing_required_fields(self, body: object, required_fields: list[str]) -> list[str]:
        if body is None:
            return required_fields
        return [field for field in required_fields if not self._has_path(body, field)]

    def _has_path(self, value: object, path: str) -> bool:
        current = value
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
                continue
            return False
        return True

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
