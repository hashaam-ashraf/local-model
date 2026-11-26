from sqlalchemy import Column, String
from sqlalchemy.orm import relationship

from app.models.abstract import AbstractModel
from app.models.tag import file_tags


class File(AbstractModel):
    """The tags of a knowledge base page. The page itself is the file under KB_ROOT."""

    __tablename__ = "files"

    path = Column(String(1024), nullable=False, unique=True)  # relative to the knowledge base folder

    tags = relationship("Tag", secondary=file_tags, lazy="selectin")
