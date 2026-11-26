from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import relationship

from app.models.abstract import AbstractModel


class Conversation(AbstractModel):
    __tablename__ = "conversations"

    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=True)  # set from the first message when not given

    messages = relationship("Message", order_by="Message.position", cascade="all, delete-orphan")


class Message(AbstractModel):
    __tablename__ = "messages"

    conversation_id = Column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)  # order within the conversation
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    sources = Column(JSON, nullable=True)  # on an answer: "page | heading" of each section the model was given
