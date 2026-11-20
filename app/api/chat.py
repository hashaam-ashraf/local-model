from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.config import Project, Settings
from app.constants.chat import MAX_HISTORY
from app.core.dependencies import get_llm, get_project, get_settings, get_store
from app.schemas.chat import chat_request
from app.services.chat_service import stream_answer
from app.services.llm_service import LLM
from app.services.store_service import Store


def create_router(models: list[str]) -> APIRouter:
    """The models come from the project files, so the request schema is built at startup."""
    router = APIRouter(tags=["chat"])
    ChatRequest = chat_request(models)

    @router.post("/{slug}/chat")
    def chat(
        body: ChatRequest,
        project: Project = Depends(get_project),
        settings: Settings = Depends(get_settings),
        llm: LLM = Depends(get_llm),
        store: Store = Depends(get_store),
    ):
        history = [m.model_dump() for m in body.messages[-MAX_HISTORY:]]
        answer = stream_answer(settings, llm, store, project, history, body.model)
        return StreamingResponse(answer, media_type="text/plain; charset=utf-8")

    return router
