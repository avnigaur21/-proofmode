from fastapi import APIRouter, HTTPException

from app.schemas.projects import ProjectProfile, ProjectProfileCreate, ProjectProfileUpdate
from app.services.project_service import project_service

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectProfile)
def create_project(payload: ProjectProfileCreate) -> ProjectProfile:
    return project_service.create_project(payload)


@router.get("", response_model=list[ProjectProfile])
def list_projects() -> list[ProjectProfile]:
    return project_service.list_projects()


@router.get("/{project_id}", response_model=ProjectProfile)
def get_project(project_id: str) -> ProjectProfile:
    project = project_service.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectProfile)
def update_project(project_id: str, payload: ProjectProfileUpdate) -> ProjectProfile:
    project = project_service.update_project(project_id, payload)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str) -> None:
    deleted = project_service.delete_project(project_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")
