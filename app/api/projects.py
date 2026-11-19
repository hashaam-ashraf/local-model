from fastapi import APIRouter, Depends

from app.config import Project
from app.core.dependencies import get_projects
from app.schemas.projects import ProjectResponse

router = APIRouter(tags=["projects"])


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(projects: dict[str, Project] = Depends(get_projects)):
    return list(projects.values())
