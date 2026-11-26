from alembic import context
from sqlalchemy import create_engine

from app import models  # noqa: F401 - registers the tables on Base.metadata
from app.config import Settings
from app.core.database import Base

engine = create_engine(Settings.from_env().database_url)
with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
