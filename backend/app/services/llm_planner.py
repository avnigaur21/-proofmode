from pydantic import BaseModel, Field, ValidationError

from app.schemas.runs import PlannedCheck, PlannerMetadata, VerificationChecklist
from app.services.git_diff_context import GitDiffContext
from app.services.llm_provider import HeuristicLlmPlannerProvider, LlmPlannerProvider


class LlmChecklistResponse(BaseModel):
    checks: list[PlannedCheck] = Field(default_factory=list)
    affected_files_hint: list[str] = Field(default_factory=list)


class LlmPlannerResult(BaseModel):
    checklist: VerificationChecklist | None = None
    metadata: PlannerMetadata
    error: str | None = None


class LlmVerificationPlanner:
    def __init__(self, provider: LlmPlannerProvider | None = None) -> None:
        self._provider = provider or HeuristicLlmPlannerProvider()

    def create_checklist(self, claim: str, diff_context: GitDiffContext | None) -> LlmPlannerResult:
        metadata = PlannerMetadata(
            mode="llm",
            source="llm",
            provider=self._provider.provider_name,
            model=self._provider.model_name,
            diff_files_used=len(diff_context.changed_files) if diff_context else 0,
            diff_truncated=diff_context.truncated if diff_context else False,
        )

        try:
            raw_response = self._provider.generate_checklist(claim, diff_context)
            parsed = LlmChecklistResponse.model_validate(raw_response)
        except (ValidationError, ValueError, TypeError) as error:
            metadata.used_fallback = True
            metadata.reason = "llm_output_invalid"
            return LlmPlannerResult(metadata=metadata, error=str(error))

        if not parsed.checks:
            metadata.used_fallback = True
            metadata.reason = "llm_returned_no_checks"
            return LlmPlannerResult(metadata=metadata, error="LLM planner returned no checks.")

        return LlmPlannerResult(
            checklist=VerificationChecklist(
                checks=parsed.checks,
                affected_files_hint=parsed.affected_files_hint,
                planner=metadata,
            ),
            metadata=metadata,
        )
