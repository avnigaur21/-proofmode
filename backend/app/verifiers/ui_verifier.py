from app.schemas.runs import CheckStatus, ProofCheck, ProofRun
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
            },
        )
