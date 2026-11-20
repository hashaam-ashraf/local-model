from typing import Literal

from pydantic import BaseModel, Field, create_model


class Message(BaseModel):
    role: Literal["user", "assistant"]  # clients cannot send system instructions
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    model: str | None = None  # one of the project's models; None means its default


def chat_request(models: list[str]) -> type[ChatRequest]:
    """ChatRequest with `model` as an enum of the models the project files allow."""
    return create_model("ChatRequest", __base__=ChatRequest, model=(Literal[tuple(models)] | None, None))
