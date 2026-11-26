from uuid import UUID

from pydantic import BaseModel

from app.schemas.tags import TagResponse


class FileResponse(BaseModel):
    path: str
    size: int
    tags: list[TagResponse]


class FileListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    files: list[FileResponse]


class FileTagsRequest(BaseModel):
    tags: list[UUID]


class UploadResponse(BaseModel):
    files: list[str]
    sections: int
