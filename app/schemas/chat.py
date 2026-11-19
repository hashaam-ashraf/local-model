from typing import Literal

from pydantic import BaseModel, Field


class Message(BaseModel):
    role: Literal["user", "assistant"]  # clients cannot send system instructions
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
