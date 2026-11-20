"""FastAPI dependencies: the shared objects created in app/main.py, and the admin check."""

import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Project, Settings
from app.services.llm_service import LLM
from app.services.store_service import Store


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_llm(request: Request) -> LLM:
    return request.app.state.llm


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_projects(request: Request) -> dict[str, Project]:
    return request.app.state.projects


def get_project(slug: str, request: Request) -> Project:
    projects = request.app.state.projects
    if slug not in projects:
        raise HTTPException(404, f"Unknown project: {slug}")
    return projects[slug]


admin_bearer = HTTPBearer(auto_error=False, description="ADMIN_TOKEN from .env")


def require_admin(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(admin_bearer)
) -> None:
    token = request.app.state.settings.admin_token
    given = credentials.credentials if credentials else ""
    if not token or not secrets.compare_digest(given.encode(), token.encode()):
        raise HTTPException(401, "Admin token required")
