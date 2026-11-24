from fastapi import APIRouter, Depends, Query, UploadFile

from app.config import Project, Settings
from app.constants.files import FILES_PAGE_SIZE, MAX_FILES_PAGE_SIZE
from app.core.dependencies import get_llm, get_project, get_settings, get_store, require_admin
from app.schemas.files import FileListResponse, UploadResponse
from app.services import file_service
from app.services.kb_service import index_pages
from app.services.llm_service import LLM
from app.services.store_service import Store

router = APIRouter(tags=["knowledge base"], dependencies=[Depends(require_admin)])


@router.get("/{slug}/files", response_model=FileListResponse)
def list_files(
    page: int = Query(1, ge=1),
    page_size: int = Query(FILES_PAGE_SIZE, ge=1, le=MAX_FILES_PAGE_SIZE),
    project: Project = Depends(get_project),
    settings: Settings = Depends(get_settings),
):
    return file_service.list_files(settings, project, page, page_size)


@router.post("/{slug}/files", response_model=UploadResponse, status_code=201)
def upload_files(
    files: list[UploadFile],
    project: Project = Depends(get_project),
    settings: Settings = Depends(get_settings),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
):
    uploads = [(f.filename or "", f.file.read(file_service.MAX_UPLOAD_BYTES + 1)) for f in files]
    saved = file_service.save_files(settings, project, uploads)
    return {"project": project.slug, "files": saved, "sections": index_pages(settings, llm, store, project, saved)}


@router.delete("/{slug}/files/{path:path}", status_code=204)
def delete_file(
    path: str,
    project: Project = Depends(get_project),
    settings: Settings = Depends(get_settings),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
):
    file_service.delete_file(settings, project, path)
    index_pages(settings, llm, store, project, [path])
