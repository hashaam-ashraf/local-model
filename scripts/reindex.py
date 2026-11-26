"""Embed every page again and rebuild the index from scratch: python -m scripts.reindex

Only needed after changing EMBEDDING_MODEL or editing pages on disk by hand. It drops the index
first and takes hours for a large knowledge base. Each page keeps the tags it has in the database.
"""

from openai import OpenAI
from qdrant_client import QdrantClient

from app.config import Settings
from app.core.database import make_sessions
from app.services.kb_service import rebuild_index
from app.services.llm_service import LLM
from app.services.store_service import Store

settings = Settings.from_env()
llm = LLM(OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key), settings.embedding_model)
store = Store(QdrantClient(url=settings.qdrant_url, timeout=300), settings.collection)
if input(f"Drop the '{settings.collection}' index and embed every page in {settings.kb_root} again? [y/N] ") == "y":
    with make_sessions(settings.database_url)() as db:
        print(f"Indexed {rebuild_index(settings, db, llm, store)} sections")
