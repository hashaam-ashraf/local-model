"""Search index: one Qdrant collection per project."""

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
    def __init__(self, client: QdrantClient):
        self.client = client

    def reset(self, project: str) -> None:
        if self.client.collection_exists(project):
            self.client.delete_collection(project)

    def add(self, project: str, sections: list[Section], vectors: list[list[float]]) -> None:
        if not sections:
            return
        if not self.client.collection_exists(project):
            self.client.create_collection(
                project, vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE)
            )
            # Removing a page filters on it; without an index that scans the whole collection.
            self.client.create_payload_index(project, "page", PayloadSchemaType.KEYWORD)
        self.client.upsert(
            project,
            points=[
                PointStruct(id=str(uuid4()), vector=vector, payload=asdict(section))
                for section, vector in zip(sections, vectors)
            ],
        )

    def remove(self, project: str, pages: list[str]) -> None:
        if pages and self.client.collection_exists(project):
            self.client.delete(
                project, Filter(must=[FieldCondition(key="page", match=MatchAny(any=pages))])
            )

    def search(self, project: str, vector: list[float], limit: int) -> list[Section]:
        if not self.client.collection_exists(project):
            return []
        hits = self.client.query_points(project, query=vector, limit=limit).points
        return [Section(**hit.payload) for hit in hits]
