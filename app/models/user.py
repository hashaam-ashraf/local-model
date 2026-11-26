from sqlalchemy import Column, String, Text
from sqlalchemy.orm import relationship

from app.models.abstract import AbstractModel
from app.models.tag import user_tags


class User(AbstractModel):
    __tablename__ = "users"

    email = Column(String(255), nullable=False, unique=True)
    name = Column(String(255), nullable=False)
    hashed_password = Column(Text, nullable=False)
    role = Column(String(50), nullable=False)

    # A user's answers come from untagged files and files that share one of these tags; admins are not limited.
    tags = relationship("Tag", secondary=user_tags, lazy="selectin")
    conversations = relationship("Conversation", cascade="all, delete-orphan")
