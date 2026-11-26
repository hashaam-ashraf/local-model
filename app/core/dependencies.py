"""FastAPI dependencies: the shared objects created in app/main.py, and who is calling."""

from collections.abc import Iterator

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.constants.roles import ADMIN
from app.core.security import read_token
from app.models import User
from app.services.llm_service import LLM
from app.services.store_service import Store


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_llm(request: Request) -> LLM:
    return request.app.state.llm


def get_store(request: Request) -> Store:
    return request.app.state.store


def get_sessions(request: Request) -> sessionmaker:
    return request.app.state.sessions


def get_db(request: Request) -> Iterator[Session]:
    with request.app.state.sessions() as db:
        yield db


bearer = HTTPBearer(auto_error=False, description="The token from POST /v1/auth/login")


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """The user is read on every request, so a changed role or tag applies to the next one."""
    secret_key = request.app.state.settings.secret_key
    user_id = read_token(secret_key, credentials.credentials) if credentials and secret_key else None
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(401, "Login required")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != ADMIN:
        raise HTTPException(403, "Admin access required")
    return user
