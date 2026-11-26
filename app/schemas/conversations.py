from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, create_model


class MessageRequest(BaseModel):
    """The client sends only its own message; the history and the system prompt come from the server."""

    message: str = Field(min_length=1)
    model: str | None = None  # one of the allowed models; None means the default
    tags: list[UUID] | None = None  # narrow the search to these tags; never widens what the user may see


def message_request(models: list[str]) -> type[MessageRequest]:
    """MessageRequest with `model` as an enum of the models the settings allow."""
    return create_model("MessageRequest", __base__=MessageRequest, model=(Literal[tuple(models)] | None, None))


class ConversationCreate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=255)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: Literal["user", "assistant"]
    content: str
    sources: list[str] | None
    created_at: datetime


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    title: str | None
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse]


class ConversationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    conversations: list[ConversationResponse]
