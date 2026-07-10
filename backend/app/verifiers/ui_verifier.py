from urllib.parse import urljoin

from app.schemas.runs import CheckStatus, PlannedCheck, ProofCheck, ProofRun
from app.services.artifacts import artifact_root, artifact_url


class UiVerifier:
    layer = "ui"

    def verify(self, run: ProofRun) -> ProofCheck:
        if run.target_url is None:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="No target URL was provided, so UI behavior was not checked.",
            )

        screenshot_dir = artifact_root() / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_filename = f"{run.id}_after.png"
        screenshot_path = screenshot_dir / screenshot_filename
        screenshot_url = artifact_url("screenshots", screenshot_filename)

        console_errors: list[str] = []
        page_errors: list[str] = []
        network_failures: list[str] = []
        target_results: list[dict[str, object]] = []
        target_issues: list[dict[str, object]] = []
        targeted_checks = self._targeted_checks(run)

        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
            from playwright.sync_api import sync_playwright
        except ImportError:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.UNCERTAIN,
                summary="Playwright is not installed yet, so UI behavior could not be checked.",
                evidence={"target_url": run.target_url},
            )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(viewport={"width": 1440, "height": 900})

                page.on(
                    "console",
                    lambda message: console_errors.append(message.text)
                    if message.type == "error"
                    else None,
                )
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.on(
                    "requestfailed",
                    lambda request: network_failures.append(
                        f"{request.method} {request.url}: {request.failure}"
                    ),
                )

                page.goto(run.target_url, wait_until="networkidle", timeout=15000)
                for check in targeted_checks:
                    if check.type == "configured_flow":
                        result, issues = self._evaluate_flow_check(page, run.target_url, check)
                    else:
                        result, issues = self._evaluate_targeted_check(page, check)
                    target_results.append(result)
                    target_issues.extend(issues)
                page.screenshot(path=str(screenshot_path), full_page=True)
                browser.close()
        except PlaywrightTimeoutError as error:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="The target page timed out during UI verification.",
                evidence={
                    "target_url": run.target_url,
                    "error": str(error),
                    "screenshot_path": str(screenshot_path),
                    "screenshot_url": screenshot_url,
                },
            )
        except Exception as error:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="Playwright could not complete UI verification.",
                evidence={
                    "target_url": run.target_url,
                    "error": str(error),
                    "screenshot_path": str(screenshot_path),
                    "screenshot_url": screenshot_url,
                },
            )

        all_errors = console_errors + page_errors + network_failures
        if target_issues:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary=f"Targeted UI verification found {len(target_issues)} issue(s).",
                evidence={
                    "target_url": run.target_url,
                    "screenshot_path": str(screenshot_path),
                    "screenshot_url": screenshot_url,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "network_failures": network_failures,
                    "target_results": target_results,
                    "issues": target_issues,
                },
            )

        if all_errors:
            return ProofCheck(
                layer=self.layer,
                status=CheckStatus.FAILED,
                summary="The page loaded, but UI verification found browser errors.",
                evidence={
                    "target_url": run.target_url,
                    "screenshot_path": str(screenshot_path),
                    "screenshot_url": screenshot_url,
                    "console_errors": console_errors,
                    "page_errors": page_errors,
                    "network_failures": network_failures,
                    "target_results": target_results,
                },
            )

        return ProofCheck(
            layer=self.layer,
            status=CheckStatus.PASSED,
            summary="The target page loaded successfully with no captured browser errors.",
            evidence={
                "target_url": run.target_url,
                "screenshot_path": str(screenshot_path),
                "screenshot_url": screenshot_url,
                "console_errors": console_errors,
                "page_errors": page_errors,
                "network_failures": network_failures,
                "target_results": target_results,
            },
        )

    def _targeted_checks(self, run: ProofRun) -> list[PlannedCheck]:
        return [
            check
            for check in run.checklist.checks
            if check.layer == self.layer
            and (
                check.assertions.get("text")
                or check.assertions.get("selector")
                or check.assertions.get("url_contains")
                or check.assertions.get("steps")
            )
        ]

    def _evaluate_flow_check(
        self, page, target_url: str, check: PlannedCheck
    ) -> tuple[dict[str, object], list[dict[str, object]]]:
        assertions = check.assertions
        flow_path = assertions.get("path")
        steps = assertions.get("steps", [])
        issues: list[dict[str, object]] = []
        step_results: list[dict[str, object]] = []

        if isinstance(flow_path, str) and flow_path:
            page.goto(self._flow_url(target_url, flow_path), wait_until="networkidle", timeout=15000)

        for index, raw_step in enumerate(steps):
            if not isinstance(raw_step, dict):
                continue
            step_result, step_issues = self._evaluate_flow_step(page, raw_step, index)
            step_results.append(step_result)
            issues.extend(step_issues)

        return (
            {
                "type": check.type,
                "target": check.target,
                "step_count": len(step_results),
                "steps": step_results,
                "current_url": page.url,
            },
            issues,
        )

    def _evaluate_flow_step(self, page, step: dict, index: int) -> tuple[dict[str, object], list[dict[str, object]]]:
        action = str(step.get("action", ""))
        selector = step.get("selector")
        text = step.get("text")
        value = step.get("value")
        url_contains = step.get("url_contains")
        result: dict[str, object] = {"index": index, "action": action}
        issues: list[dict[str, object]] = []

        try:
            if action == "click" and isinstance(selector, str):
                page.locator(selector).first.click(timeout=5000)
                result["selector"] = selector
                result["clicked"] = True
            elif action == "fill" and isinstance(selector, str):
                page.locator(selector).first.fill(str(value or ""), timeout=5000)
                result["selector"] = selector
                result["filled"] = True
            elif action == "expect_text" and isinstance(text, str):
                count = page.get_by_text(text).count()
                result["text"] = text
                result["text_found"] = count > 0
                if count == 0:
                    issues.append({"type": "flow_text_not_found", "step": index, "text": text, "severity": "high"})
            elif action == "expect_selector" and isinstance(selector, str):
                locator = page.locator(selector)
                count = locator.count()
                visible = count > 0 and locator.first.is_visible()
                result["selector"] = selector
                result["selector_count"] = count
                result["selector_visible"] = visible
                if not visible:
                    issues.append(
                        {"type": "flow_selector_not_visible", "step": index, "selector": selector, "severity": "high"}
                    )
            elif action == "expect_url" and isinstance(url_contains, str):
                result["current_url"] = page.url
                result["expected_contains"] = url_contains
                if url_contains not in page.url:
                    issues.append(
                        {
                            "type": "flow_url_assertion_failed",
                            "step": index,
                            "expected_contains": url_contains,
                            "actual": page.url,
                            "severity": "medium",
                        }
                    )
            else:
                issues.append({"type": "flow_step_invalid", "step": index, "action": action, "severity": "medium"})
        except Exception as error:
            issues.append(
                {
                    "type": "flow_step_failed",
                    "step": index,
                    "action": action,
                    "selector": selector,
                    "error": str(error),
                    "severity": "high",
                }
            )

        return result, issues

    def _evaluate_targeted_check(self, page, check: PlannedCheck) -> tuple[dict[str, object], list[dict[str, object]]]:
        assertions = check.assertions
        issues: list[dict[str, object]] = []
        result: dict[str, object] = {
            "type": check.type,
            "target": check.target,
            "assertions": assertions,
        }

        expected_text = assertions.get("text")
        if isinstance(expected_text, str) and expected_text:
            text_found = page.get_by_text(expected_text).count() > 0
            result["text_found"] = text_found
            if not text_found:
                issues.append(
                    {
                        "type": "text_not_found",
                        "text": expected_text,
                        "severity": "high",
                    }
                )

        selector = assertions.get("selector")
        if isinstance(selector, str) and selector:
            locator = page.locator(selector)
            selector_count = locator.count()
            is_visible = selector_count > 0 and locator.first.is_visible()
            result["selector_count"] = selector_count
            result["selector_visible"] = is_visible
            if selector_count == 0:
                issues.append(
                    {
                        "type": "selector_not_found",
                        "selector": selector,
                        "severity": "high",
                    }
                )
            elif assertions.get("visible", True) and not is_visible:
                issues.append(
                    {
                        "type": "selector_not_visible",
                        "selector": selector,
                        "severity": "high",
                    }
                )

        url_contains = assertions.get("url_contains")
        if isinstance(url_contains, str) and url_contains:
            current_url = page.url
            result["current_url"] = current_url
            if url_contains not in current_url:
                issues.append(
                    {
                        "type": "url_assertion_failed",
                        "expected_contains": url_contains,
                        "actual": current_url,
                        "severity": "medium",
                    }
                )

        return result, issues

    def _flow_url(self, target_url: str, path: str) -> str:
        if path.startswith("http://") or path.startswith("https://"):
            return path
        return urljoin(target_url.rstrip("/") + "/", path.lstrip("/"))
