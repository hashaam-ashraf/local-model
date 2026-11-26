"""App entrypoint: shared clients, CORS and router registration."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from qdrant_client import QdrantClient
from sqlalchemy.orm import sessionmaker

from app.api.auth import router as auth_router
from app.api.conversations import create_router as create_conversations_router
from app.api.files import router as files_router
from app.api.tags import router as tags_router
from app.api.users import router as users_router
from app.config import Settings
from app.core.database import make_sessions
from app.services.conversation_service import allowed_models
from app.services.llm_service import LLM
from app.services.store_service import Store

API_V1_PREFIX = "/v1"


def create_app(
    settings: Settings | None = None,
    llm: LLM | None = None,
    store: Store | None = None,
    sessions: sessionmaker | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()

    app = FastAPI(title="local-model")
    app.state.settings = settings
    app.state.llm = llm or LLM(
        OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key), settings.embedding_model
    )
    app.state.store = store or Store(QdrantClient(url=settings.qdrant_url), settings.collection)
    app.state.sessions = sessions or make_sessions(settings.database_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    app.include_router(auth_router, prefix=API_V1_PREFIX)
    app.include_router(users_router, prefix=API_V1_PREFIX)
    app.include_router(tags_router, prefix=API_V1_PREFIX)
    app.include_router(create_conversations_router(allowed_models(settings)), prefix=API_V1_PREFIX)
    app.include_router(files_router, prefix=API_V1_PREFIX)
    return app
