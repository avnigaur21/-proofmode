from app.schemas.runs import (
    CheckStatus,
    ProofRun,
    SelfReportComparison,
    SelfReportMismatch,
    SelfReportVerdict,
    VerificationLayer,
)


class SelfReportComparator:
    def compare(self, run: ProofRun) -> SelfReportComparison:
        report = (run.agent_report or "").strip()
        if not report:
            return SelfReportComparison()

        normalized_report = report.lower()
        detected = self._detected_claims(normalized_report)
        mismatches: list[SelfReportMismatch] = []
        supported: list[str] = []

        for topic in detected:
            mismatch = self._mismatch_for(topic, report, run)
            if mismatch:
                mismatches.append(mismatch)
            else:
                supported.append(self._supported_statement(topic))

        verdict = self._verdict(mismatches)
        return SelfReportComparison(
            verdict=verdict,
            confidence=self._confidence(detected, mismatches),
            summary=self._summary(verdict, detected, mismatches),
            detected_claims=detected,
            mismatches=mismatches,
            supported_statements=supported,
        )

    def _detected_claims(self, report: str) -> list[str]:
        topics: list[str] = []
        keyword_groups = {
            "tests": ("test", "pytest", "unit test", "integration test", "suite passed"),
            "ui": ("frontend", "page", "screen", "button", "click", "browser", "playwright"),
            "api": ("api", "endpoint", "route", "request", "response", "contract"),
            "db": ("database", "db", "migration", "table", "row", "schema"),
            "diff": ("changed", "commit", "git", "diff", "files"),
            "screenshots": ("screenshot", "screen capture", "visual evidence"),
        }

        for topic, keywords in keyword_groups.items():
            if any(keyword in report for keyword in keywords):
                topics.append(topic)

        return topics or ["general"]

    def _mismatch_for(
        self,
        topic: str,
        report: str,
        run: ProofRun,
    ) -> SelfReportMismatch | None:
        if topic in {"ui", "api", "db", "diff"}:
            return self._layer_mismatch(topic, report, run)

        if topic == "tests":
            tests_check = next((check for check in run.checks if check.layer == "tests"), None)
            if tests_check and tests_check.status == CheckStatus.PASSED:
                return None
            if tests_check and tests_check.status == CheckStatus.FAILED:
                return SelfReportMismatch(
                    topic=topic,
                    severity="critical",
                    agent_statement=self._excerpt(report),
                    evidence_status=tests_check.status,
                    explanation=f"The agent mentioned tests, but captured test evidence failed: {tests_check.summary}",
                )
            return SelfReportMismatch(
                topic=topic,
                severity="warning",
                agent_statement=self._excerpt(report),
                evidence_status="not_verified",
                explanation="The agent mentioned tests, but ProofMode did not capture passing test command evidence.",
            )

        if topic == "screenshots":
            screenshot_available = any(check.evidence.get("screenshot_path") for check in run.checks)
            if not screenshot_available:
                return SelfReportMismatch(
                    topic=topic,
                    severity="warning",
                    agent_statement=self._excerpt(report),
                    evidence_status="not_verified",
                    explanation="The agent mentioned screenshots or visual evidence, but no screenshot artifact was captured.",
                )
            return None

        if run.evaluation and run.evaluation.verdict == "supported":
            return None

        return SelfReportMismatch(
            topic=topic,
            severity="warning",
            agent_statement=self._excerpt(report),
            evidence_status=run.evaluation.verdict if run.evaluation else run.status,
            explanation="The self-report made a broad completion statement, but ProofMode evidence is not fully supported.",
        )

    def _layer_mismatch(
        self,
        layer: VerificationLayer,
        report: str,
        run: ProofRun,
    ) -> SelfReportMismatch | None:
        check = next((check for check in run.checks if check.layer == layer), None)

        if check is None:
            return SelfReportMismatch(
                topic=layer,
                severity="warning",
                agent_statement=self._excerpt(report),
                evidence_status="not_checked",
                explanation=f"The agent mentioned {layer.upper()} work, but ProofMode did not execute a {layer.upper()} check.",
            )

        if check.status == CheckStatus.FAILED:
            return SelfReportMismatch(
                topic=layer,
                severity="critical",
                agent_statement=self._excerpt(report),
                evidence_status=check.status,
                explanation=f"The agent mentioned {layer.upper()} work, but the {layer.upper()} proof check failed: {check.summary}",
            )

        if check.status == CheckStatus.UNCERTAIN:
            return SelfReportMismatch(
                topic=layer,
                severity="warning",
                agent_statement=self._excerpt(report),
                evidence_status=check.status,
                explanation=f"The agent mentioned {layer.upper()} work, but the {layer.upper()} proof check was inconclusive: {check.summary}",
            )

        return None

    def _verdict(self, mismatches: list[SelfReportMismatch]) -> SelfReportVerdict:
        if not mismatches:
            return SelfReportVerdict.ALIGNED
        if any(mismatch.severity == "critical" for mismatch in mismatches):
            return SelfReportVerdict.CONTRADICTED
        return SelfReportVerdict.PARTIALLY_UNSUPPORTED

    def _confidence(self, detected: list[str], mismatches: list[SelfReportMismatch]) -> float:
        if not detected:
            return 0.3
        if not mismatches:
            return 0.82
        if any(mismatch.severity == "critical" for mismatch in mismatches):
            return 0.9
        return 0.74

    def _summary(
        self,
        verdict: SelfReportVerdict,
        detected: list[str],
        mismatches: list[SelfReportMismatch],
    ) -> str:
        if verdict == SelfReportVerdict.ALIGNED:
            return "The agent self-report aligns with the executed ProofMode evidence."
        if verdict == SelfReportVerdict.CONTRADICTED:
            return "The agent self-report is contradicted by at least one failed ProofMode check."
        return (
            f"ProofMode detected {len(detected)} self-report topic(s), with "
            f"{len(mismatches)} unsupported or unverified statement(s)."
        )

    def _supported_statement(self, topic: str) -> str:
        return f"{topic} statement is supported by executed ProofMode evidence."

    def _excerpt(self, report: str) -> str:
        single_line = " ".join(report.split())
        return single_line[:240]


self_report_comparator = SelfReportComparator()
