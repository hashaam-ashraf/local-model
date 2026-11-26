"""SQLAlchemy base, the session factory app/main.py builds once, and paging for list queries."""

from sqlalchemy import Select, create_engine, func, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

Base = declarative_base()


def make_sessions(url: str) -> sessionmaker:
    return sessionmaker(bind=create_engine(url, pool_pre_ping=True))


def paginate(db: Session, query: Select, page: int, page_size: int, key: str) -> dict:
    """One page of the query's rows under `key`, with the total across all pages."""
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    rows = list(db.scalars(query.offset((page - 1) * page_size).limit(page_size)))
    return {"total": total, "page": page, "page_size": page_size, key: rows}
