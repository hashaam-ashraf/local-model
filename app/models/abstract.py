import uuid

from sqlalchemy import Column, DateTime, Uuid
from sqlalchemy.sql import func

from app.core.database import Base


class AbstractModel(Base):
    __abstract__ = True

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
