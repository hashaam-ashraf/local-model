"""Knowledge base pages on disk: list, upload and delete."""

from fastapi import HTTPException

from app.config import Project, Settings
from app.constants.files import MAX_UPLOAD_MB
from app.services.kb_service import kb_folder, list_pages

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def list_files(settings: Settings, project: Project, page: int, page_size: int) -> dict:
    pages = list(list_pages(kb_folder(settings, project)).items())
    shown = pages[(page - 1) * page_size : page * page_size]
    files = [{"path": name, "size": path.stat().st_size} for name, path in shown]
    return {"total": len(pages), "page": page, "page_size": page_size, "files": files}


def save_files(settings: Settings, project: Project, uploads: list[tuple[str, bytes]]) -> list[str]:
    """Save uploaded pages into the top level of the project's knowledge base folder.

    A page with the same name is replaced. Nothing is written unless every file is valid.
    """
    root = kb_folder(settings, project)
    pages = {}
    for filename, content in uploads:
        name = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if not name.endswith(".md") or name.startswith("."):
            raise HTTPException(400, f"{name or 'File'}: only markdown (.md) files can be uploaded")
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"{name}: larger than {MAX_UPLOAD_MB} MB")
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, f"{name}: not UTF-8 text")
        pages[name] = content

    root.mkdir(parents=True, exist_ok=True)
    for name, content in pages.items():
        (root / name).write_bytes(content)
    return sorted(pages)


def delete_file(settings: Settings, project: Project, path: str) -> None:
    pages = list_pages(kb_folder(settings, project))
    if path not in pages:
        raise HTTPException(404, f"No such file: {path}")
    pages[path].unlink()
