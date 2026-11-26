from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.dependencies import get_current_user, get_db, get_settings
from app.models import User
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.users import UserResponse
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, settings: Settings = Depends(get_settings), db: Session = Depends(get_db)):
    return {"token": user_service.login(settings, db, body.email, body.password)}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
