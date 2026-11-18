"""Markdown knowledge base pages split into sections by heading."""

import re
from dataclasses import dataclass
from pathlib import Path

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


def load_sections(root: Path) -> list[Section]:
    sections = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        sections += split_page(rel.as_posix(), path.read_text(encoding="utf-8"))
    return sections
