"""Settings from the environment."""

import os
from pathlib import Path

from pydantic import BaseModel, field_validator


class Settings(BaseModel):
    llm_base_url: str = "http://ollama:11434/v1"
    llm_api_key: str = "ollama"  # Ollama ignores it; a hosted API needs a real one
    default_model: str = "gemma3:4b"
    models: list[str] = []  # other models a client may ask for
    embedding_model: str = "bge-m3"
    system_prompt: str = "You are a helpful assistant. Be concise and practical."
    top_k: int = 5  # sections given to the model per question
    allowed_origins: list[str] = []  # sites allowed to call the api from a browser
    qdrant_url: str = "http://qdrant:6333"
    collection: str = "kb"  # the Qdrant collection holding the index
    kb_root: Path = Path("kb")
    database_url: str = "postgresql+psycopg2://local_model:local_model@postgres:5432/local_model"
    secret_key: str = ""  # signs login tokens; empty rejects every login
    admin_email: str = ""  # the admin seeded at startup; none is seeded while either is empty
    admin_password: str = ""

    @field_validator("models", "allowed_origins", mode="before")
    @classmethod
    def split(cls, value):
        """The environment holds a list as comma-separated text."""
        return [v.strip() for v in value.split(",") if v.strip()] if isinstance(value, str) else value

    @classmethod
    def from_env(cls) -> "Settings":
        values = {name: os.environ.get(name.upper()) for name in cls.model_fields}
        return cls(**{name: value for name, value in values.items() if value})
