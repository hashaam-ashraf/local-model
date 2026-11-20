from fastapi import APIRouter, Depends

from app.config import Project, Settings
from app.core.dependencies import get_projects, get_settings
from app.schemas.projects import ProjectResponse
from app.services.chat_service import project_models

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    projects: dict[str, Project] = Depends(get_projects),
    settings: Settings = Depends(get_settings),
):
    return [
        ProjectResponse(slug=p.slug, name=p.name, models=project_models(settings, p))
        for p in projects.values()
    ]
