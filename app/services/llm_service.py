"""Chat and embeddings over the OpenAI-compatible API (Ollama by default)."""

from collections.abc import Iterator

from openai import OpenAI

EMBED_BATCH = 32


class LLM:
    def __init__(self, client: OpenAI, embedding_model: str):
        self.client = client
        self.embedding_model = embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = texts[start : start + EMBED_BATCH]
            result = self.client.embeddings.create(model=self.embedding_model, input=batch)
            vectors += [item.embedding for item in result.data]
        return vectors

    def stream_chat(self, model: str, messages: list[dict]) -> Iterator[str]:
        stream = self.client.chat.completions.create(model=model, messages=messages, stream=True)
        for event in stream:
            if event.choices and event.choices[0].delta.content:
                yield event.choices[0].delta.content
