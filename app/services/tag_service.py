"""Tags: the labels that decide which files a user's answers may come from."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import paginate
from app.models import Tag, file_tags, user_tags
from app.schemas.tags import TagCreate


def list_tags(db: Session, page: int, page_size: int) -> dict:
    return paginate(db, select(Tag).order_by(Tag.name), page, page_size, "tags")


def get_tags(db: Session, ids: list[UUID]) -> list[Tag]:
    tags = list(db.scalars(select(Tag).where(Tag.id.in_(ids)))) if ids else []
    if len(tags) != len(set(ids)):
        raise HTTPException(400, "Unknown tag")
    return tags


def create_tag(db: Session, data: TagCreate) -> Tag:
    name = data.name.strip()
    if db.scalar(select(Tag).where(Tag.name == name)):
        raise HTTPException(409, f"Tag already exists: {name}")
    tag = Tag(name=name, description=data.description)
    db.add(tag)
    db.commit()
    return tag


def delete_tag(db: Session, tag_id: UUID) -> None:
    """The index keeps the id on its sections, which is harmless: no user can hold a deleted tag."""
    tag = db.get(Tag, tag_id)
    if not tag:
        raise HTTPException(404, "No such tag")
    db.execute(delete(user_tags).where(user_tags.c.tag_id == tag_id))
    db.execute(delete(file_tags).where(file_tags.c.tag_id == tag_id))
    db.delete(tag)
    db.commit()
