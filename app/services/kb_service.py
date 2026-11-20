"""Markdown knowledge base pages split into sections by heading, and indexing them."""

import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException

from app.config import Project, Settings

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


def kb_folder(settings: Settings, project: Project) -> Path:
    if not project.kb_path:
        raise HTTPException(400, f"Project {project.slug} has no knowledge base")
    return settings.kb_root / project.kb_path


def list_pages(root: Path) -> dict[str, Path]:
    """Markdown pages under root, keyed by their path relative to it. Hidden folders and files are skipped."""
    pages = {}
    if root.is_dir():
        for path in sorted(root.rglob("*.md")):
            rel = path.relative_to(root)
            if path.is_file() and not any(part.startswith(".") for part in rel.parts):
                pages[rel.as_posix()] = path
    return pages


def load_sections(root: Path) -> list[Section]:
    sections = []
    for page, path in list_pages(root).items():
        sections += split_page(page, path.read_text(encoding="utf-8"))
    return sections


def rebuild_index(settings: Settings, llm, store, project: Project) -> int:
    sections = load_sections(kb_folder(settings, project))
    store.replace(project.slug, sections, llm.embed([s.content for s in sections]))
    return len(sections)
