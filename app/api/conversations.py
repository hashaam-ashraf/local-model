from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.constants.pagination import MAX_PAGE_SIZE, PAGE_SIZE
from app.core.dependencies import get_current_user, get_db, get_llm, get_sessions, get_settings, get_store
from app.models import User
from app.schemas.conversations import (
    ConversationCreate,
    ConversationDetailResponse,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdate,
    message_request,
)
from app.services import conversation_service
from app.services.llm_service import LLM
from app.services.store_service import Store

def create_router(models: list[str]) -> APIRouter:
    """The models come from the settings, so the request schema is built at startup."""
    router = APIRouter(tags=["conversations"], dependencies=[Depends(get_current_user)])
    MessageRequest = message_request(models)

    @router.get("/models", response_model=list[str])
    def list_models():
        """The models a message may name, the default first."""
        return models

    @router.get("/conversations", response_model=ConversationListResponse)
    def list_conversations(
        page: int = Query(1, ge=1),
        page_size: int = Query(PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return conversation_service.list_conversations(db, user, page, page_size)

    @router.post("/conversations", response_model=ConversationResponse, status_code=201)
    def create_conversation(
        body: ConversationCreate | None = None,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return conversation_service.create_conversation(db, user, body.title if body else None)

    @router.get("/conversations/{conversation_id}", response_model=ConversationDetailResponse)
    def get_conversation(
        conversation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        return conversation_service.get_conversation(db, user, conversation_id)

    @router.post("/conversations/{conversation_id}/messages")
    def send_message(
        conversation_id: UUID,
        body: MessageRequest,
        user: User = Depends(get_current_user),
        settings: Settings = Depends(get_settings),
        db: Session = Depends(get_db),
        llm: LLM = Depends(get_llm),
        store: Store = Depends(get_store),
        sessions: sessionmaker = Depends(get_sessions),
    ):
        """Streams the reply as plain text. The earlier messages are read on the server."""
        conversation = conversation_service.get_conversation(db, user, conversation_id)
        answer = conversation_service.stream_answer(
            settings, llm, store, sessions, user, conversation, body.message, body.model, body.tags
        )
        return StreamingResponse(answer, media_type="text/plain; charset=utf-8")

    @router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
    def rename_conversation(
        conversation_id: UUID,
        body: ConversationUpdate,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ):
        return conversation_service.rename_conversation(db, user, conversation_id, body.title)

    @router.delete("/conversations/{conversation_id}", status_code=204)
    def delete_conversation(
        conversation_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)
    ):
        conversation_service.delete_conversation(db, user, conversation_id)

    return router
