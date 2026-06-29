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
            )
        ]

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
