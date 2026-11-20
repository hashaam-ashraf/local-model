from pydantic import BaseModel


class FileResponse(BaseModel):
    path: str
    size: int


class UploadResponse(BaseModel):
    project: str
    files: list[str]
    sections: int
