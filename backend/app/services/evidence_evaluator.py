from app.schemas.runs import CheckStatus, EvidenceEvaluation, EvidenceVerdict, ProofRun


class EvidenceEvaluator:
    def evaluate(self, run: ProofRun) -> EvidenceEvaluation:
        if not run.checks:
            return EvidenceEvaluation(
                verdict=EvidenceVerdict.INSUFFICIENT,
                confidence=0.7,
                explanation="No automated proof checks ran, so the claim cannot be evaluated.",
                reasons=["No UI, API, DB, or Git diff evidence was available."],
                guardrails=["Evaluator cannot mark a claim supported without executed proof checks."],
            )

        failed_checks = [check for check in run.checks if check.status == CheckStatus.FAILED]
        if failed_checks:
            failed_layers = ", ".join(check.layer.upper() for check in failed_checks)
            return EvidenceEvaluation(
                verdict=EvidenceVerdict.CONTRADICTED,
                confidence=0.95,
                explanation=(
                    f"Deterministic proof failed in {failed_layers}, so the claim is contradicted "
                    "until those failures are resolved."
                ),
                reasons=[f"{check.layer.upper()}: {check.summary}" for check in failed_checks],
                guardrails=[
                    "Deterministic verifier failures cannot be overridden by evaluator judgment.",
                    "A failed UI/API/DB/Git proof keeps the claim from being marked supported.",
                ],
            )

        uncertain_checks = [check for check in run.checks if check.status == CheckStatus.UNCERTAIN]
        if uncertain_checks:
            uncertain_layers = ", ".join(check.layer.upper() for check in uncertain_checks)
            return EvidenceEvaluation(
                verdict=EvidenceVerdict.INSUFFICIENT,
                confidence=0.72,
                explanation=(
                    f"Proof evidence is incomplete or inconclusive in {uncertain_layers}, so the claim "
                    "is not fully supported yet."
                ),
                reasons=[f"{check.layer.upper()}: {check.summary}" for check in uncertain_checks],
                guardrails=[
                    "Uncertain proof results require human review or stronger targeted checks.",
                    "Evaluator does not upgrade inconclusive evidence to supported.",
                ],
            )

        return EvidenceEvaluation(
            verdict=EvidenceVerdict.SUPPORTED,
            confidence=0.82,
            explanation=(
                "All executed deterministic proof checks passed, so the available evidence supports "
                "the agent's completion claim."
            ),
            reasons=[f"{check.layer.upper()}: {check.summary}" for check in run.checks],
            guardrails=[
                "Supported means supported by executed checks, not a guarantee that untested behavior is correct.",
                "Human approval can still require additional evidence before accepting the run.",
            ],
        )
