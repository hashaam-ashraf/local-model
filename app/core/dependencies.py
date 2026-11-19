"""FastAPI dependencies: the shared objects created in app/main.py, and the admin check."""

import secrets

from fastapi import Header, HTTPException, Request

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


def require_admin(request: Request, authorization: str = Header("")) -> None:
    token = request.app.state.settings.admin_token
    expected = f"Bearer {token}"
    if not token or not secrets.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "Admin token required")
