"""Conversations: answering a message (retrieval, prompt building, streaming) and the stored history."""

from collections.abc import Iterator
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.constants.conversations import MAX_HISTORY, TITLE_LENGTH
from app.constants.prompts import KB_RULES
from app.constants.roles import ADMIN
from app.core.database import paginate
from app.models import Conversation, Message, User
from app.services.kb_service import Section
from app.services.llm_service import LLM
from app.services.store_service import Store


def allowed_models(settings: Settings) -> list[str]:
    """The models a client may use, the default first."""
    return list(dict.fromkeys([settings.default_model, *settings.models]))


def list_conversations(db: Session, user: User, page: int, page_size: int) -> dict:
    """A user's own conversations, newest first; an admin gets everyone's."""
    query = select(Conversation).order_by(Conversation.created_at.desc(), Conversation.id)
    if user.role != ADMIN:
        query = query.where(Conversation.user_id == user.id)
    return paginate(db, query, page, page_size, "conversations")


def get_conversation(db: Session, user: User, conversation_id: UUID) -> Conversation:
    """Someone else's conversation is reported as missing, so ids cannot be probed."""
    conversation = db.get(Conversation, conversation_id)
    if not conversation or (user.role != ADMIN and conversation.user_id != user.id):
        raise HTTPException(404, "No such conversation")
    return conversation


def create_conversation(db: Session, user: User, title: str | None) -> Conversation:
    conversation = Conversation(user_id=user.id, title=title)
    db.add(conversation)
    db.commit()
    return conversation


def rename_conversation(db: Session, user: User, conversation_id: UUID, title: str) -> Conversation:
    conversation = get_conversation(db, user, conversation_id)
    conversation.title = title
    db.commit()
    return conversation


def delete_conversation(db: Session, user: User, conversation_id: UUID) -> None:
    db.delete(get_conversation(db, user, conversation_id))
    db.commit()


def build_messages(settings: Settings, sections: list[Section], history: list[dict]) -> list[dict]:
    listed = "\n\n".join(f"[{s.page} | {s.heading}]\n{s.text}" for s in sections)
    system = (
        f"{settings.system_prompt.strip()}\n\n{KB_RULES}\n\n"
        f"Knowledge base sections:\n\n{listed or '(no section matched this question)'}"
    )
    return [{"role": "system", "content": system}, *history]


def search_tags(user: User, requested: list[UUID] | None) -> list[str] | None:
    """The tag ids a search is limited to; None means no limit. A user never reaches past their own tags."""
    if user.role == ADMIN:
        return None if requested is None else [str(tag) for tag in requested]
    own = [tag.id for tag in user.tags]
    return [str(tag) for tag in own if requested is None or tag in requested]


def stream_answer(
    settings: Settings,
    llm: LLM,
    store: Store,
    sessions: sessionmaker,
    user: User,
    conversation: Conversation,
    message: str,
    model: str | None = None,
    tags: list[UUID] | None = None,
) -> Iterator[str]:
    """Answer the next message of a conversation.

    The message and its answer are saved together once the reply has streamed, so a failed reply leaves nothing.
    """
    conversation_id, position, untitled = conversation.id, len(conversation.messages), not conversation.title
    history = [{"role": m.role, "content": m.content} for m in conversation.messages]
    history.append({"role": "user", "content": message})

    sections = store.search(llm.embed([message])[0], settings.top_k, search_tags(user, tags))
    messages = build_messages(settings, sections, history[-MAX_HISTORY:])

    def generate():
        parts = []
        for piece in llm.stream_chat(model or settings.default_model, messages):
            parts.append(piece)
            yield piece
        sources = [f"{s.page} | {s.heading}" for s in sections]
        # The request's own session is gone once the reply has streamed, so this opens one.
        with sessions() as db:
            if untitled:
                db.get(Conversation, conversation_id).title = message.strip()[:TITLE_LENGTH]
            db.add(Message(conversation_id=conversation_id, position=position, role="user", content=message))
            db.add(
                Message(
                    conversation_id=conversation_id,
                    position=position + 1,
                    role="assistant",
                    content="".join(parts),
                    sources=sources,
                )
            )
            db.commit()

    return generate()
