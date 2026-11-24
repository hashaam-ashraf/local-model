from pydantic import BaseModel


class FileResponse(BaseModel):
    path: str
    size: int


class FileListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    files: list[FileResponse]


class UploadResponse(BaseModel):
    project: str
    files: list[str]
    sections: int
