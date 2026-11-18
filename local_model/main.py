"""FastAPI app: per-project chat and knowledge base indexing."""

import secrets
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_client import QdrantClient

from . import chatlog
from .chat import build_messages
from .config import Project, Settings, load_projects
from .kb import load_sections
from .llm import LLM
from .store import Store

MAX_HISTORY = 20


class Message(BaseModel):
    role: Literal["user", "assistant"]  # clients cannot send system instructions
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


def create_app(settings: Settings | None = None, llm: LLM | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    projects = load_projects(settings.projects_dir)
    llm = llm or LLM(
        OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key), settings.embedding_model
    )
    store = store or Store(QdrantClient(url=settings.qdrant_url))

    app = FastAPI(title="local-model")
    origins = sorted({origin for p in projects.values() for origin in p.allowed_origins})
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["POST"], allow_headers=["*"])

    def get_project(slug: str) -> Project:
        if slug not in projects:
            raise HTTPException(404, f"Unknown project: {slug}")
        return projects[slug]

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/v1/projects")
    def list_projects():
        return [{"slug": p.slug, "name": p.name} for p in projects.values()]

    @app.post("/v1/{slug}/chat")
    def chat(slug: str, body: ChatRequest):
        project = get_project(slug)
        history = [m.model_dump() for m in body.messages[-MAX_HISTORY:]]
        if history[-1]["role"] != "user":
            raise HTTPException(400, "The last message must be from the user")
        question = history[-1]["content"]

        sections = []
        if project.kb_path:
            sections = store.search(slug, llm.embed([question])[0], project.top_k)
        messages = build_messages(project, sections, history)

        def generate():
            parts = []
            for piece in llm.stream_chat(project.model or settings.default_model, messages):
                parts.append(piece)
                yield piece
            sources = [f"{s.page} | {s.heading}" for s in sections]
            chatlog.save(settings.chat_log, slug, question, "".join(parts), sources)

        return StreamingResponse(generate(), media_type="text/plain; charset=utf-8")

    @app.post("/v1/{slug}/index")
    def index(slug: str, authorization: str = Header("")):
        expected = f"Bearer {settings.admin_token}"
        if not settings.admin_token or not secrets.compare_digest(authorization.encode(), expected.encode()):
            raise HTTPException(401, "Admin token required")
        project = get_project(slug)
        if not project.kb_path:
            raise HTTPException(400, f"Project {slug} has no knowledge base")
        sections = load_sections(settings.kb_root / project.kb_path)
        store.replace(slug, sections, llm.embed([s.content for s in sections]))
        return {"project": slug, "sections": len(sections)}

    app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True))
    return app
