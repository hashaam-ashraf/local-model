"""Settings from the environment and per-project config from projects/*.toml."""

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    llm_base_url: str = "http://ollama:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores it; a hosted API needs a real one
    default_model: str = "gemma3:4b"
    embedding_model: str = "bge-m3"
    qdrant_url: str = "http://qdrant:6333"
    projects_dir: Path = Path("projects")
    kb_root: Path = Path("kb")
    chat_log: Path = Path("data/chats.sqlite")
    admin_token: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        values = {name: os.environ.get(name.upper()) for name in cls.model_fields}
        return cls(**{name: value for name, value in values.items() if value})


class Project(BaseModel):
    slug: str
    name: str
    system_prompt: str
    model: str | None = None
    models: list[str] = []  # other models a client may ask for
    kb_path: str | None = None  # folder under kb_root; None means no knowledge base
    top_k: int = 5
    allowed_origins: list[str] = []


def load_projects(directory: Path) -> dict[str, Project]:
    projects = {}
    for path in sorted(directory.glob("*.toml")):
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        projects[path.stem] = Project(slug=path.stem, **data)
    return projects
