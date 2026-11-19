"""Answering a question: retrieval, prompt building, streaming and the chat log."""

from collections.abc import Iterator

from fastapi import HTTPException

from app.config import Project, Settings
from app.constants.prompts import KB_RULES
from app.services import chatlog_service
from app.services.kb_service import Section
from app.services.llm_service import LLM
from app.services.store_service import Store


def build_messages(project: Project, sections: list[Section], history: list[dict]) -> list[dict]:
    """Project prompts set the persona; the knowledge base rules are shared."""
    system = project.system_prompt.strip()
    if project.kb_path:
        listed = "\n\n".join(f"[{s.page} | {s.heading}]\n{s.text}" for s in sections)
        system += f"\n\n{KB_RULES}\n\nKnowledge base sections:\n\n{listed or '(no section matched this question)'}"
    return [{"role": "system", "content": system}, *history]


def stream_answer(
    settings: Settings, llm: LLM, store: Store, project: Project, history: list[dict]
) -> Iterator[str]:
    if history[-1]["role"] != "user":
        raise HTTPException(400, "The last message must be from the user")
    question = history[-1]["content"]

    sections = []
    if project.kb_path:
        sections = store.search(project.slug, llm.embed([question])[0], project.top_k)
    messages = build_messages(project, sections, history)

    def generate():
        parts = []
        for piece in llm.stream_chat(project.model or settings.default_model, messages):
            parts.append(piece)
            yield piece
        sources = [f"{s.page} | {s.heading}" for s in sections]
        chatlog_service.save(settings.chat_log, project.slug, question, "".join(parts), sources)

    return generate()
