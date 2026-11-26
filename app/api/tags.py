from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.constants.pagination import MAX_PAGE_SIZE, PAGE_SIZE
from app.core.dependencies import get_db, require_admin
from app.schemas.tags import TagCreate, TagListResponse, TagResponse
from app.services import tag_service

router = APIRouter(prefix="/tags", tags=["tags"], dependencies=[Depends(require_admin)])


@router.get("", response_model=TagListResponse)
def list_tags(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
):
    return tag_service.list_tags(db, page, page_size)


@router.post("", response_model=TagResponse, status_code=201)
def create_tag(body: TagCreate, db: Session = Depends(get_db)):
    return tag_service.create_tag(db, body)


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: UUID, db: Session = Depends(get_db)):
    tag_service.delete_tag(db, tag_id)
