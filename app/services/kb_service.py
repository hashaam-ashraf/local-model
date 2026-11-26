"""Markdown knowledge base pages split into sections by heading, and indexing them."""

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import File, file_tags

HEADING = re.compile(r"^(#{1,6})\s+(.*)")


@dataclass
class Section:
    page: str
    heading: str  # heading trail, e.g. "Fees > Refunds"
    text: str

    @property
    def content(self) -> str:
        return f"{self.heading}\n{self.text}".strip()


def split_page(page: str, text: str) -> list[Section]:
    sections: list[Section] = []
    trail: list[tuple[int, str]] = []
    lines: list[str] = []
    in_fence = False

    def flush():
        body = "\n".join(lines).strip()
        if body:
            sections.append(Section(page, " > ".join(title for _, title in trail), body))
        lines.clear()

    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        match = None if in_fence else HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            trail[:] = [(lvl, title) for lvl, title in trail if lvl < level]
            trail.append((level, match.group(2).strip()))
        else:
            lines.append(line)
    flush()
    return sections


def list_pages(root: Path) -> dict[str, Path]:
    """Markdown pages under root, keyed by their path relative to it. Hidden folders and files are skipped."""
    pages = {}
    if root.is_dir():
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(root)
            if path.is_file() and not any(part.startswith(".") for part in rel.parts):
                pages[rel.as_posix()] = path
    return pages


def page_tags(db: Session, pages: list[str] | None = None) -> dict[str, list[str]]:
    """Tag ids by page, as the index stores them. A page without tags is left out."""
    query = select(File.path, file_tags.c.tag_id).join(file_tags, file_tags.c.file_id == File.id)
    if pages is not None:
        query = query.where(File.path.in_(pages))
    tags: dict[str, list[str]] = {}
    for path, tag_id in db.execute(query):
        tags.setdefault(path, []).append(str(tag_id))
    return tags


def _index_page(llm, store, page: str, path: Path, tags: list[str]) -> int:
    sections = split_page(page, path.read_text(encoding="utf-8"))
    store.add(sections, llm.embed([s.content for s in sections]), tags)
    return len(sections)


def rebuild_index(settings: Settings, db: Session, llm, store) -> int:
    """Index every page from scratch, one page at a time so a large knowledge base never sits in memory."""
    pages = list_pages(settings.kb_root)
    tags = page_tags(db)
    store.reset()
    return sum(_index_page(llm, store, page, path, tags.get(page, [])) for page, path in pages.items())


def index_pages(settings: Settings, db: Session, llm, store, pages: list[str]) -> int:
    """Bring the index in line with the named pages only: uploaded, replaced or deleted."""
    on_disk = list_pages(settings.kb_root)
    tags = page_tags(db, pages)
    store.remove(pages)
    return sum(_index_page(llm, store, page, on_disk[page], tags.get(page, [])) for page in pages if page in on_disk)
