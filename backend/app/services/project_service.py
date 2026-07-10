from datetime import datetime, timezone

from app.schemas.projects import ProjectProfile, ProjectProfileCreate, ProjectProfileUpdate
from app.services.project_store import ProjectStore


class ProjectService:
    def __init__(self) -> None:
        self._store = ProjectStore()
        self._projects: dict[str, ProjectProfile] = self._store.load_all()

    def create_project(self, payload: ProjectProfileCreate) -> ProjectProfile:
        project = ProjectProfile(
            name=payload.name,
            repo_path=payload.repo_path,
            target_url=payload.target_url,
            api_base_url=payload.api_base_url,
            target_db_url=payload.target_db_url,
            api_checks=payload.api_checks,
            ui_flows=payload.ui_flows,
            test_commands=payload.test_commands,
            default_run_config=payload.default_run_config,
        )
        self._projects[project.id] = project
        self._store.save(project)
        return project

    def list_projects(self) -> list[ProjectProfile]:
        return sorted(self._projects.values(), key=lambda project: project.updated_at, reverse=True)

    def get_project(self, project_id: str) -> ProjectProfile | None:
        return self._projects.get(project_id)

    def update_project(self, project_id: str, payload: ProjectProfileUpdate) -> ProjectProfile | None:
        project = self._projects.get(project_id)
        if project is None:
            return None

        updates = {field: getattr(payload, field) for field in payload.model_fields_set}
        updated_project = project.model_copy(
            update={
                **updates,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        self._projects[updated_project.id] = updated_project
        self._store.save(updated_project)
        return updated_project

    def delete_project(self, project_id: str) -> bool:
        if project_id not in self._projects:
            return False

        del self._projects[project_id]
        self._store.delete(project_id)
        return True


project_service = ProjectService()
