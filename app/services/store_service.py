"""Search index: one Qdrant collection. Each section carries the tag ids of its page."""

from dataclasses import asdict
from uuid import uuid4

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from app.services.kb_service import Section


class Store:
    def __init__(self, client: QdrantClient, collection: str):
        self.client = client
        self.collection = collection

    def exists(self) -> bool:
        return self.client.collection_exists(self.collection)

    def reset(self) -> None:
        if self.exists():
            self.client.delete_collection(self.collection)

    def add(self, sections: list[Section], vectors: list[list[float]], tags: list[str]) -> None:
        if not sections:
            return
        if not self.exists():
            self.client.create_collection(
                self.collection, vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE)
            )
            # Removing a page filters on it; without an index that scans the whole collection.
            self.client.create_payload_index(self.collection, "page", PayloadSchemaType.KEYWORD)
            self.index_tags()
        self.client.upsert(
            self.collection,
            points=[
                PointStruct(id=str(uuid4()), vector=vector, payload={**asdict(section), "tags": tags})
                for section, vector in zip(sections, vectors)
            ],
        )

    def _pages(self, pages: list[str]) -> Filter:
        return Filter(must=[FieldCondition(key="page", match=MatchAny(any=pages))])

    def remove(self, pages: list[str]) -> None:
        if pages and self.exists():
            self.client.delete(self.collection, self._pages(pages))

    def index_tags(self) -> None:
        """Every search by a user filters on tags; a collection made before tags existed needs this once."""
        if self.exists():
            self.client.create_payload_index(self.collection, "tags", PayloadSchemaType.KEYWORD)

    def set_tags(self, pages: list[str], tags: list[str]) -> None:
        """Relabel the indexed sections of these pages. Nothing is embedded again."""
        if pages and self.exists():
            self.client.set_payload(self.collection, payload={"tags": tags}, points=self._pages(pages))

    def search(self, vector: list[float], limit: int, tags: list[str] | None) -> list[Section]:
        """The closest sections carrying one of the tags. None searches everything; no tags finds nothing."""
        if tags == [] or not self.exists():
            return []
        only = tags and Filter(must=[FieldCondition(key="tags", match=MatchAny(any=tags))])
        hits = self.client.query_points(self.collection, query=vector, limit=limit, query_filter=only).points
        return [Section(hit.payload["page"], hit.payload["heading"], hit.payload["text"]) for hit in hits]
