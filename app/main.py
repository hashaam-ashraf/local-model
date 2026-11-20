"""App entrypoint: shared clients, CORS, router registration and the demo page."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from qdrant_client import QdrantClient

from app.api.chat import create_router as create_chat_router
from app.api.files import router as files_router
from app.api.kb import router as kb_router
from app.api.projects import router as projects_router
from app.config import Settings, load_projects
from app.services.chat_service import project_models
from app.services.llm_service import LLM
from app.services.store_service import Store

API_V1_PREFIX = "/v1"


def create_app(settings: Settings | None = None, llm: LLM | None = None, store: Store | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    projects = load_projects(settings.projects_dir)

    app = FastAPI(title="local-model")
    app.state.settings = settings
    app.state.projects = projects
    app.state.llm = llm or LLM(
        OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key), settings.embedding_model
    )
    app.state.store = store or Store(QdrantClient(url=settings.qdrant_url))

    origins = sorted({origin for p in projects.values() for origin in p.allowed_origins})
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["POST"], allow_headers=["*"])

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(projects_router, prefix=API_V1_PREFIX)
    models = [settings.default_model, *(m for p in projects.values() for m in project_models(settings, p))]
    app.include_router(create_chat_router(list(dict.fromkeys(models))), prefix=API_V1_PREFIX)
    app.include_router(kb_router, prefix=API_V1_PREFIX)
    app.include_router(files_router, prefix=API_V1_PREFIX)

    app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True))
    return app
