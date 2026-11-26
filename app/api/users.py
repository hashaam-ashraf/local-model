from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.pagination import MAX_PAGE_SIZE, PAGE_SIZE
from app.core.dependencies import get_db, require_admin
from app.models import User
from app.schemas.users import UserCreate, UserListResponse, UserResponse, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=UserListResponse, dependencies=[Depends(require_admin)])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    return user_service.list_users(db, page, page_size)


@router.post("", response_model=UserResponse, status_code=201, dependencies=[Depends(require_admin)])
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    return user_service.create_user(db, body)


@router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID, body: UserUpdate, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    return user_service.update_user(db, admin, user_id, body)


@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: UUID, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user_service.delete_user(db, admin, user_id)
