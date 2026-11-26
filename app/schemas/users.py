from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.constants.auth import MAX_PASSWORD, MIN_PASSWORD
from app.constants.roles import ADMIN, USER
from app.schemas.tags import TagResponse

Role = Literal[ADMIN, USER]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=MIN_PASSWORD, max_length=MAX_PASSWORD)
    role: Role = USER
    tags: list[UUID] = []


class UserUpdate(BaseModel):
    """Only the fields sent are changed."""

    name: str | None = Field(None, min_length=1, max_length=255)
    password: str | None = Field(None, min_length=MIN_PASSWORD, max_length=MAX_PASSWORD)
    role: Role | None = None
    tags: list[UUID] | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: Role
    tags: list[TagResponse]


class UserListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    users: list[UserResponse]
