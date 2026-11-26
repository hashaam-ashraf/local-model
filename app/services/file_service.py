"""Knowledge base pages on disk and their tags in the database: list, upload, tag and delete."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.constants.files import MAX_UPLOAD_MB, TAG_BATCH
from app.models import File, Tag
from app.services import tag_service
from app.services.kb_service import list_pages, page_tags
from app.services.store_service import Store

MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024


def _rows(db: Session, paths: list[str]) -> dict[str, File]:
    return {row.path: row for row in db.scalars(select(File).where(File.path.in_(paths)))}


def list_files(settings: Settings, db: Session, page: int, page_size: int) -> dict:
    pages = list(list_pages(settings.kb_root).items())
    shown = pages[(page - 1) * page_size : page * page_size]
    rows = _rows(db, [name for name, _ in shown])
    files = [
        {"path": name, "size": path.stat().st_size, "tags": rows[name].tags if name in rows else []}
        for name, path in shown
    ]
    return {"total": len(pages), "page": page, "page_size": page_size, "files": files}


def save_files(settings: Settings, db: Session, uploads: list[tuple[str, bytes]], tag_ids: list[UUID]) -> list[str]:
    """Save uploaded pages into the top level of the knowledge base folder, with these tags.

    A page with the same name is replaced, and so are its tags. Nothing is written unless every file is valid.
    """
    tags = tag_service.get_tags(db, tag_ids)
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

    settings.kb_root.mkdir(parents=True, exist_ok=True)
    rows = _rows(db, list(pages))
    for name, content in pages.items():
        (settings.kb_root / name).write_bytes(content)
        row = rows.get(name) or File(path=name)
        row.tags = tags
        db.add(row)
    db.commit()
    return sorted(pages)


def set_tags(settings: Settings, db: Session, store: Store, path: str, tag_ids: list[UUID]) -> dict:
    """Replace a page's tags, in the database and on its indexed sections."""
    pages = list_pages(settings.kb_root)
    if path not in pages:
        raise HTTPException(404, f"No such file: {path}")
    row = _rows(db, [path]).get(path) or File(path=path)
    row.tags = tag_service.get_tags(db, tag_ids)
    db.add(row)
    db.flush()
    # The index first: if it fails, nothing is committed and the request can simply be repeated.
    store.set_tags([path], [str(tag.id) for tag in row.tags])
    db.commit()
    return {"path": path, "size": pages[path].stat().st_size, "tags": row.tags}


def delete_file(settings: Settings, db: Session, path: str) -> None:
    pages = list_pages(settings.kb_root)
    if path not in pages:
        raise HTTPException(404, f"No such file: {path}")
    pages[path].unlink()
    row = _rows(db, [path]).get(path)
    if row:
        db.delete(row)
        db.commit()


def import_files(settings: Settings, db: Session, store: Store, tag_names: list[str]) -> int:
    """Give every page on disk a row, then copy the tags in the database onto the index.

    For pages that were indexed before tags existed, or changed on disk by hand. Nothing is embedded,
    and it is safe to repeat: only pages without a row get the named tags, which are created if missing.
    """
    pages = list(list_pages(settings.kb_root))
    known = set(db.scalars(select(File.path)))
    new = [page for page in pages if page not in known]
    tags = []
    for name in tag_names:
        tag = db.scalar(select(Tag).where(Tag.name == name)) or Tag(name=name)
        db.add(tag)
        tags.append(tag)
    db.add_all(File(path=page, tags=tags) for page in new)
    db.commit()

    store.index_tags()
    by_page = page_tags(db)
    groups: dict[tuple[str, ...], list[str]] = {}
    for page in pages:
        groups.setdefault(tuple(sorted(by_page.get(page, []))), []).append(page)
    for tag_ids, tagged in groups.items():
        for start in range(0, len(tagged), TAG_BATCH):
            store.set_tags(tagged[start : start + TAG_BATCH], list(tag_ids))
    return len(new)
