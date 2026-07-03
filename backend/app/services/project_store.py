import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.projects import ProjectProfile
from app.services.artifacts import artifact_root


class ProjectStore:
    def __init__(self) -> None:
        self._projects_dir = artifact_root() / "projects"
        self._projects_dir.mkdir(parents=True, exist_ok=True)

    def save(self, project: ProjectProfile) -> None:
        project_path = self._project_path(project.id)
        project_path.write_text(
            json.dumps(project.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def load_all(self) -> dict[str, ProjectProfile]:
        projects: dict[str, ProjectProfile] = {}

        for project_path in sorted(self._projects_dir.glob("*.json")):
            try:
                project = ProjectProfile.model_validate_json(project_path.read_text(encoding="utf-8"))
            except (OSError, ValidationError, ValueError):
                continue

            projects[project.id] = project

        return projects

    def delete(self, project_id: str) -> None:
        project_path = self._project_path(project_id)
        if project_path.exists():
            project_path.unlink()

    def _project_path(self, project_id: str) -> Path:
        return self._projects_dir / f"{project_id}.json"
