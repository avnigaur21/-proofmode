from app.schemas.runs import ProofRun


class VerificationPlanner:
    def create_checklist(self, run: ProofRun) -> dict[str, list[dict[str, str]]]:
        return {
            "ui_checks": [],
            "api_checks": [],
            "data_checks": [],
            "affected_files_hint": [],
        }

