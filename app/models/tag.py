from sqlalchemy import Column, ForeignKey, String, Table, Text

from app.core.database import Base
from app.models.abstract import AbstractModel


class Tag(AbstractModel):
    __tablename__ = "tags"

    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)


user_tags = Table(
    "user_tags",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

file_tags = Table(
    "file_tags",
    Base.metadata,
    Column("file_id", ForeignKey("files.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)
