import socket

import pytest
from fastapi.testclient import TestClient
from qdrant_client import QdrantClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import Settings
from app.core.database import Base
from app.core.security import create_token
from app.main import create_app
from app.services.kb_service import rebuild_index
from app.models import User
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
    """The app with a fake model, an in-memory index and a temp database; the client is logged in as an admin."""
    kb = tmp_path / "kb"
    kb.mkdir()
    (kb / "money.md").write_text(
        "# Refunds\n\nA refund takes 5 days.\n\n# Fees\n\nThe fee is 1 percent.\n", encoding="utf-8"
    )
    settings = Settings(
        kb_root=kb,
        secret_key="test-secret-key-of-at-least-32-bytes",
        default_model="small-model",
        models=["tiny-model"],
        system_prompt="You are the demo assistant.",
        top_k=1,
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite'}")
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        admin = User(email="admin@example.com", name="Admin", hashed_password="-", role="admin")
        db.add(admin)
        db.commit()
        token = create_token(settings.secret_key, admin.id)
    llm = FakeLLM()
    client = TestClient(create_app(settings, llm, Store(QdrantClient(":memory:"), "kb"), sessions))
    client.headers["Authorization"] = f"Bearer {token}"
    return client, llm, settings


@pytest.fixture
def as_user(env):
    """Create a user holding the named tags (made if missing) and return their login headers."""
    client = env[0]

    def create(email, *tag_names):
        known = {tag["name"]: tag["id"] for tag in client.get("/v1/tags").json()["tags"]}
        ids = [known.get(n) or client.post("/v1/tags", json={"name": n}).json()["id"] for n in tag_names]
        body = {"email": email, "name": "User", "password": "password1", "tags": ids}
        assert client.post("/v1/users", json=body).status_code == 201
        token = client.post("/v1/auth/login", json={"email": email, "password": "password1"}).json()["token"]
        return {"Authorization": f"Bearer {token}"}

    return create


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Tests use a fake model and an in-memory index; any real connection is a bug."""

    def blocked(*args, **kwargs):
        raise RuntimeError("Network access is blocked in tests")

    monkeypatch.setattr(socket.socket, "connect", blocked)


@pytest.fixture
def reindex(env):
    """Index the pages on disk from scratch, as scripts/reindex.py does."""
    client, llm, settings = env

    def run():
        with client.app.state.sessions() as db:
            return rebuild_index(settings, db, llm, client.app.state.store)

    return run
