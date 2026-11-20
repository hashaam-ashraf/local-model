import socket

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient

from app.config import Settings
from app.main import create_app
from app.services.store_service import Store

WORDS = ["refund", "fee", "card", "limit"]


class FakeLLM:
    def __init__(self):
        self.embedded = []
        self.chats = []

    def embed(self, texts):
        self.embedded += texts
        return [[0.01 + text.lower().count(word) for word in WORDS] for text in texts]

    def stream_chat(self, model, messages):
        self.chats.append((model, messages))
        yield "Hello"
        yield " there"


@pytest.fixture
def env(tmp_path):
    projects = tmp_path / "projects"
    projects.mkdir()
    (projects / "demo.toml").write_text(
        'name = "Demo"\nsystem_prompt = "You are the demo assistant."\nkb_path = "demo-kb"\ntop_k = 1\n',
        encoding="utf-8",
    )
    (projects / "plain.toml").write_text(
        'name = "Plain"\nsystem_prompt = "You are a plain assistant."\nmodel = "big-model"\n',
        encoding="utf-8",
    )
    kb = tmp_path / "kb" / "demo-kb"
    kb.mkdir(parents=True)
    (kb / "money.md").write_text(
        "# Refunds\n\nA refund takes 5 days.\n\n# Fees\n\nThe fee is 1 percent.\n", encoding="utf-8"
    )
    settings = Settings(
        projects_dir=projects,
        kb_root=tmp_path / "kb",
        chat_log=tmp_path / "data" / "chats.sqlite",
        admin_token="secret",
        default_model="small-model",
    )
    llm = FakeLLM()
    client = TestClient(create_app(settings, llm, Store(QdrantClient(":memory:"))))
    return client, llm, settings


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests use a fake model and an in-memory index; any real connection is a bug."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)
