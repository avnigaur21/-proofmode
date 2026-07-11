import json
import os
from typing import Any, Protocol

import httpx

from app.schemas.runs import CheckStatus, EvaluationRubricScore, EvidenceEvaluation, EvidenceVerdict, ProofRun


class EvidenceEvaluatorProvider(Protocol):
    provider_name: str
    model_name: str | None

    def evaluate(self, run: ProofRun) -> dict[str, Any]:
        ...


class HeuristicEvidenceEvaluatorProvider:
    provider_name = "heuristic"
    model_name = "local-evidence-heuristic-v1"

    def evaluate(self, run: ProofRun) -> dict[str, Any]:
        return {
            "verdict": "supported",
            "confidence": 0.8,
            "explanation": (
                "The local evaluator found that all executed checks passed and no deterministic "
                "contradictions were present."
            ),
            "reasons": [f"{check.layer.upper()}: {check.summary}" for check in run.checks],
            "guardrails": [],
            "rubrics": self._rubrics(run),
        }

    def _rubrics(self, run: ProofRun) -> list[dict[str, Any]]:
        return [
            {
                "name": "claim_coverage",
                "score": 0.78,
                "label": "Good",
                "explanation": "Executed checks cover the configured proof layers for the claim.",
            },
            {
                "name": "evidence_completeness",
                "score": 0.76,
                "label": "Good",
                "explanation": f"{len(run.checks)} proof check(s) produced usable evidence.",
            },
        ]


class OpenAiEvidenceEvaluatorProvider:
    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name or os.getenv("PROOFMODE_LLM_MODEL", "gpt-4.1-mini")
        self._base_url = (base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")).rstrip("/")
        self._http_client = http_client or httpx.Client(timeout=30)

    def evaluate(self, run: ProofRun) -> dict[str, Any]:
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is required when PROOFMODE_LLM_PROVIDER=openai.")

        response = self._http_client.post(
            f"{self._base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=self._request_payload(run),
        )
        response.raise_for_status()
        return self._parse_response(response.json())

    def _request_payload(self, run: ProofRun) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are ProofMode's evidence evaluator. Decide whether the proof evidence "
                        "supports the AI agent's completion claim. You must not override deterministic "
                        "verifier failures. Return JSON only."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "claim": run.claim,
                            "agent_report": run.agent_report,
                            "self_report_comparison": run.self_report_comparison.model_dump(mode="json")
                            if run.self_report_comparison
                            else None,
                            "checklist": [check.model_dump(mode="json") for check in run.checklist.checks],
                            "checks": [self._check_summary(check) for check in run.checks],
                            "required_output": {
                                "verdict": "supported | contradicted | insufficient",
                                "confidence": "number between 0 and 1",
                                "explanation": "short explanation",
                                "reasons": ["specific evidence-based reason"],
                                "guardrails": ["safety or limitation note"],
                                "rubrics": [
                                    {
                                        "name": "claim_coverage",
                                        "score": "number between 0 and 1",
                                        "label": "Weak | Partial | Good | Strong",
                                        "explanation": "why this score was assigned",
                                    }
                                ],
                            },
                        },
                        indent=2,
                    ),
                },
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "proofmode_evidence_evaluation",
                    "strict": True,
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "verdict": {
                                "type": "string",
                                "enum": ["supported", "contradicted", "insufficient"],
                            },
                            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            "explanation": {"type": "string"},
                            "reasons": {"type": "array", "items": {"type": "string"}},
                            "guardrails": {"type": "array", "items": {"type": "string"}},
                            "rubrics": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "properties": {
                                        "name": {"type": "string"},
                                        "score": {"type": "number", "minimum": 0, "maximum": 1},
                                        "label": {"type": "string"},
                                        "explanation": {"type": "string"},
                                    },
                                    "required": ["name", "score", "label", "explanation"],
                                },
                            },
                        },
                        "required": ["verdict", "confidence", "explanation", "reasons", "guardrails", "rubrics"],
                    },
                },
            },
        }

    def _check_summary(self, check) -> dict[str, Any]:
        evidence = check.evidence
        return {
            "layer": check.layer,
            "status": check.status,
            "summary": check.summary,
            "evidence_keys": sorted(evidence.keys()),
            "issues": evidence.get("issues", []),
            "changed_files": evidence.get("changed_files", [])[:10]
            if isinstance(evidence.get("changed_files"), list)
            else [],
            "recommended_layers": evidence.get("recommended_layers", []),
        }

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise ValueError("OpenAI evaluator response did not include message content.") from error

        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenAI evaluator response content was empty.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("OpenAI evaluator response was not valid JSON.") from error

        if not isinstance(parsed, dict):
            raise ValueError("OpenAI evaluator response JSON must be an object.")

        return parsed


def create_evidence_evaluator_provider() -> EvidenceEvaluatorProvider:
    provider = os.getenv("PROOFMODE_LLM_PROVIDER", "heuristic").lower()
    if provider == "openai":
        return OpenAiEvidenceEvaluatorProvider()
    return HeuristicEvidenceEvaluatorProvider()


class EvidenceEvaluator:
    def __init__(self, mode: str | None = None, provider: EvidenceEvaluatorProvider | None = None) -> None:
        self._mode = mode or os.getenv("PROOFMODE_EVALUATOR_MODE", "deterministic")
        self._provider = provider or create_evidence_evaluator_provider()

    def evaluate(self, run: ProofRun) -> EvidenceEvaluation:
        if not run.checks:
            return EvidenceEvaluation(
                verdict=EvidenceVerdict.INSUFFICIENT,
                confidence=0.7,
                explanation="No automated proof checks ran, so the claim cannot be evaluated.",
                reasons=["No UI, API, DB, or Git diff evidence was available."],
                guardrails=["Evaluator cannot mark a claim supported without executed proof checks."],
                rubrics=self._rubrics_for(run),
                evaluator_mode=self._guarded_mode(),
                provider=self._provider.provider_name,
                model=self._provider.model_name,
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
                    "A failed UI/API/DB/Git/tests proof keeps the claim from being marked supported.",
                ],
                rubrics=self._rubrics_for(run),
                evaluator_mode=self._guarded_mode(),
                provider=self._provider.provider_name,
                model=self._provider.model_name,
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
                rubrics=self._rubrics_for(run),
                evaluator_mode=self._guarded_mode(),
                provider=self._provider.provider_name,
                model=self._provider.model_name,
            )

        deterministic = EvidenceEvaluation(
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
            rubrics=self._rubrics_for(run),
            provider=self._provider.provider_name,
            model=self._provider.model_name,
        )

        if self._mode != "llm":
            return deterministic

        return self._evaluate_with_llm(run, deterministic)

    def _evaluate_with_llm(self, run: ProofRun, fallback: EvidenceEvaluation) -> EvidenceEvaluation:
        try:
            raw_evaluation = self._provider.evaluate(run)
            evaluation = EvidenceEvaluation.model_validate(
                {
                    **raw_evaluation,
                    "evaluator_mode": "llm",
                    "provider": self._provider.provider_name,
                    "model": self._provider.model_name,
                }
            )
        except Exception:
            return fallback.model_copy(
                update={
                    "evaluator_mode": "deterministic_fallback",
                    "guardrails": [
                        *fallback.guardrails,
                        "LLM evidence evaluator failed or returned invalid output; deterministic evaluation was used.",
                    ],
                }
            )

        evaluation.guardrails = [
            *evaluation.guardrails,
            "LLM evaluation only runs after deterministic checks avoid failed or uncertain results.",
            "Deterministic verifier failures cannot be overridden by LLM judgment.",
        ]
        return evaluation

    def _guarded_mode(self) -> str:
        return "guarded_deterministic" if self._mode == "llm" else "deterministic"

    def _rubrics_for(self, run: ProofRun) -> list[EvaluationRubricScore]:
        return [
            self._rubric(
                "claim_coverage",
                self._claim_coverage_score(run),
                "How well executed checks cover the agent's claim.",
            ),
            self._rubric(
                "ui_proof_strength",
                self._layer_score(run, "ui"),
                "Strength of browser/UI evidence.",
            ),
            self._rubric(
                "api_proof_strength",
                self._layer_score(run, "api"),
                "Strength of API contract evidence.",
            ),
            self._rubric(
                "db_proof_strength",
                self._layer_score(run, "db"),
                "Strength of database state evidence.",
            ),
            self._rubric(
                "git_diff_relevance",
                self._layer_score(run, "diff"),
                "Whether changed-code evidence was inspected.",
            ),
            self._rubric(
                "test_evidence_strength",
                self._layer_score(run, "tests"),
                "Strength of captured test command evidence.",
            ),
            self._rubric(
                "evidence_completeness",
                self._evidence_completeness_score(run),
                "Overall completeness across enabled proof layers.",
            ),
        ]

    def _rubric(self, name: str, score: float, explanation_prefix: str) -> EvaluationRubricScore:
        bounded_score = max(0, min(score, 1))
        label = self._score_label(bounded_score)
        return EvaluationRubricScore(
            name=name,
            score=bounded_score,
            label=label,
            explanation=f"{explanation_prefix} {label.lower()} confidence based on executed proof results.",
        )

    def _claim_coverage_score(self, run: ProofRun) -> float:
        if not run.checklist.checks:
            return 0.15
        executed_layers = {check.layer for check in run.checks}
        planned_layers = {check.layer for check in run.checklist.checks}
        if not planned_layers:
            return 0.2
        return len(executed_layers.intersection(planned_layers)) / len(planned_layers)

    def _layer_score(self, run: ProofRun, layer: str) -> float:
        if not run.run_config.is_layer_enabled(layer):  # type: ignore[arg-type]
            return 0.5

        check = next((check for check in run.checks if check.layer == layer), None)
        if check is None:
            return 0.15
        if check.status == CheckStatus.PASSED:
            return 0.88
        if check.status == CheckStatus.UNCERTAIN:
            return 0.45
        return 0.05

    def _evidence_completeness_score(self, run: ProofRun) -> float:
        enabled_layers = [
            layer
            for layer in ("ui", "api", "db", "diff", "tests")
            if run.run_config.is_layer_enabled(layer)  # type: ignore[arg-type]
        ]
        if not enabled_layers:
            return 0.1

        executed_layers = {check.layer for check in run.checks}
        return len(executed_layers.intersection(enabled_layers)) / len(enabled_layers)

    def _score_label(self, score: float) -> str:
        if score >= 0.85:
            return "Strong"
        if score >= 0.65:
            return "Good"
        if score >= 0.35:
            return "Partial"
        return "Weak"
