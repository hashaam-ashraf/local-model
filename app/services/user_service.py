"""Users: logging in, and the admin's list, create, update and delete."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants.roles import ADMIN
from app.core.database import paginate
from app.core.security import create_token, hash_password, verify_password
from app.models import User
from app.schemas.users import UserCreate, UserUpdate
from app.services import tag_service


def login(settings: Settings, db: Session, email: str, password: str) -> str:
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not settings.secret_key or not user or not verify_password(password, user.hashed_password):
        raise HTTPException(401, "Wrong email or password")
    return create_token(settings.secret_key, user.id)


def list_users(db: Session, page: int, page_size: int) -> dict:
    return paginate(db, select(User).order_by(User.email), page, page_size, "users")


def create_user(db: Session, data: UserCreate) -> User:
    email = data.email.strip().lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(409, f"User already exists: {email}")
    user = User(
        email=email,
        name=data.name,
        hashed_password=hash_password(data.password),
        role=data.role,
        tags=tag_service.get_tags(db, data.tags),
    )
    db.add(user)
    db.commit()
    return user


def seed_admin(db: Session, email: str, password: str) -> bool:
    """Create this admin unless the email is taken. An existing user is left as is, password included."""
    if db.scalar(select(User).where(User.email == email.strip().lower())):
        return False
    create_user(db, UserCreate(email=email, name="Admin", password=password, role=ADMIN))
    return True


def _get(db: Session, user_id: UUID) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "No such user")
    return user


def update_user(db: Session, admin: User, user_id: UUID, data: UserUpdate) -> User:
    user = _get(db, user_id)
    if data.role and data.role != ADMIN and user.id == admin.id:
        raise HTTPException(400, "You cannot remove your own admin role")
    if data.name:
        user.name = data.name
    if data.password:
        user.hashed_password = hash_password(data.password)
    if data.role:
        user.role = data.role
    if data.tags is not None:
        user.tags = tag_service.get_tags(db, data.tags)
    db.commit()
    return user


def delete_user(db: Session, admin: User, user_id: UUID) -> None:
    user = _get(db, user_id)
    if user.id == admin.id:
        raise HTTPException(400, "You cannot delete your own account")
    db.delete(user)
    db.commit()
