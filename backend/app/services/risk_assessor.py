from app.schemas.runs import (
    CheckStatus,
    EvidenceVerdict,
    RiskAssessment,
    RiskFactor,
    RiskLevel,
    SelfReportVerdict,
    ProofRun,
)


class RiskAssessor:
    def assess(self, run: ProofRun) -> RiskAssessment:
        factors = self._factors(run)
        score = min(sum(factor.points for factor in factors), 100)
        level = self._level(score, factors)

        return RiskAssessment(
            level=level,
            score=score,
            summary=self._summary(level, factors),
            factors=factors,
            recommended_action=self._recommended_action(level),
        )

    def _factors(self, run: ProofRun) -> list[RiskFactor]:
        factors: list[RiskFactor] = []

        for check in run.checks:
            if check.status == CheckStatus.FAILED:
                factors.append(
                    RiskFactor(
                        name=f"{check.layer}_failed",
                        severity=RiskLevel.CRITICAL,
                        points=35,
                        explanation=f"{check.layer.upper()} proof failed: {check.summary}",
                    )
                )
            elif check.status == CheckStatus.UNCERTAIN:
                factors.append(
                    RiskFactor(
                        name=f"{check.layer}_uncertain",
                        severity=RiskLevel.HIGH,
                        points=22,
                        explanation=f"{check.layer.upper()} proof was inconclusive: {check.summary}",
                    )
                )

        enabled_layers = {
            layer
            for layer in ("ui", "api", "db", "diff", "tests")
            if run.run_config.is_layer_enabled(layer)  # type: ignore[arg-type]
        }
        executed_layers = {check.layer for check in run.checks}
        missing_layers = sorted(enabled_layers - executed_layers)
        for layer in missing_layers:
            factors.append(
                RiskFactor(
                    name=f"{layer}_missing",
                    severity=RiskLevel.HIGH,
                    points=20,
                    explanation=f"{layer.upper()} verification was enabled but no check result was recorded.",
                )
            )

        if run.evaluation:
            if run.evaluation.verdict == EvidenceVerdict.CONTRADICTED:
                factors.append(
                    RiskFactor(
                        name="evaluator_contradicted",
                        severity=RiskLevel.CRITICAL,
                        points=30,
                        explanation="Evidence evaluator says the claim is contradicted.",
                    )
                )
            elif run.evaluation.verdict == EvidenceVerdict.INSUFFICIENT:
                factors.append(
                    RiskFactor(
                        name="evaluator_insufficient",
                        severity=RiskLevel.HIGH,
                        points=20,
                        explanation="Evidence evaluator says the claim has insufficient support.",
                    )
                )

        if run.self_report_comparison:
            if run.self_report_comparison.verdict == SelfReportVerdict.CONTRADICTED:
                factors.append(
                    RiskFactor(
                        name="self_report_contradicted",
                        severity=RiskLevel.CRITICAL,
                        points=25,
                        explanation="Agent self-report is contradicted by ProofMode evidence.",
                    )
                )
            elif run.self_report_comparison.verdict == SelfReportVerdict.PARTIALLY_UNSUPPORTED:
                factors.append(
                    RiskFactor(
                        name="self_report_partially_unsupported",
                        severity=RiskLevel.MEDIUM,
                        points=12,
                        explanation="Agent self-report contains unsupported or unverified statements.",
                    )
                )

        diff_check = next((check for check in run.checks if check.layer == "diff"), None)
        recommended_layers = set(diff_check.evidence.get("recommended_layers", [])) if diff_check else set()
        unchecked_recommended = sorted(recommended_layers - executed_layers)
        if unchecked_recommended:
            factors.append(
                RiskFactor(
                    name="recommended_layers_unchecked",
                    severity=RiskLevel.MEDIUM,
                    points=10,
                    explanation=(
                        "Git diff recommended additional proof layers that did not run: "
                        + ", ".join(layer.upper() for layer in unchecked_recommended)
                    ),
                )
            )

        if run.run_config.approval_required and run.approval is None:
            factors.append(
                RiskFactor(
                    name="approval_pending",
                    severity=RiskLevel.MEDIUM,
                    points=8,
                    explanation="Human approval is required but no approval decision has been recorded.",
                )
            )

        if not factors:
            factors.append(
                RiskFactor(
                    name="no_material_risk_detected",
                    severity=RiskLevel.LOW,
                    points=0,
                    explanation="No failed, uncertain, missing, or contradicted evidence was detected.",
                )
            )

        return factors

    def _level(self, score: int, factors: list[RiskFactor]) -> RiskLevel:
        if any(factor.severity == RiskLevel.CRITICAL for factor in factors) or score >= 70:
            return RiskLevel.CRITICAL
        if score >= 40:
            return RiskLevel.HIGH
        if score >= 15:
            return RiskLevel.MEDIUM
        return RiskLevel.LOW

    def _summary(self, level: RiskLevel, factors: list[RiskFactor]) -> str:
        if level == RiskLevel.LOW:
            return "Low approval risk based on the executed proof evidence."
        if level == RiskLevel.MEDIUM:
            return "Medium approval risk; review remaining gaps before accepting the claim."
        if level == RiskLevel.HIGH:
            return "High approval risk; stronger or additional proof is needed before acceptance."
        return "Critical approval risk; deterministic evidence or evaluator findings block acceptance."

    def _recommended_action(self, level: RiskLevel) -> str:
        if level == RiskLevel.LOW:
            return "Proceed to human approval if the reviewer accepts the proof scope."
        if level == RiskLevel.MEDIUM:
            return "Review highlighted factors and consider one more targeted check."
        if level == RiskLevel.HIGH:
            return "Request fixes or additional verification before approval."
        return "Do not approve until failed or contradicted evidence is resolved."


risk_assessor = RiskAssessor()
