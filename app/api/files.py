from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants.pagination import MAX_PAGE_SIZE, PAGE_SIZE
from app.core.dependencies import get_db, get_llm, get_settings, get_store, require_admin
from app.schemas.files import FileListResponse, FileResponse, FileTagsRequest, UploadResponse
from app.services import file_service
from app.services.kb_service import index_pages
from app.services.llm_service import LLM
from app.services.store_service import Store

router = APIRouter(prefix="/files", tags=["knowledge base"], dependencies=[Depends(require_admin)])


@router.get("", response_model=FileListResponse)
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
):
    return file_service.list_files(settings, db, page, page_size)


@router.post("", response_model=UploadResponse, status_code=201)
def upload_files(
    files: list[UploadFile],
    tags: list[UUID] = Form([]),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
):
    uploads = [(f.filename or "", f.file.read(file_service.MAX_UPLOAD_BYTES + 1)) for f in files]
    saved = file_service.save_files(settings, db, uploads, tags)
    return {"files": saved, "sections": index_pages(settings, db, llm, store, saved)}


@router.put("/{path:path}", response_model=FileResponse)
def set_file_tags(
    path: str,
    body: FileTagsRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    store: Store = Depends(get_store),
):
    return file_service.set_tags(settings, db, store, path, body.tags)


@router.delete("/{path:path}", status_code=204)
def delete_file(
    path: str,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
):
    file_service.delete_file(settings, db, path)
    index_pages(settings, db, llm, store, [path])
