"""Search index: one Qdrant collection per project."""

from dataclasses import asdict

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from .kb import Section


class Store:
    def __init__(self, client: QdrantClient):
        self.client = client

    def replace(self, project: str, sections: list[Section], vectors: list[list[float]]) -> None:
        if self.client.collection_exists(project):
            self.client.delete_collection(project)
        if not sections:
            return
        self.client.create_collection(
            project, vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE)
        )
        self.client.upsert(
            project,
            points=[
                PointStruct(id=i, vector=vector, payload=asdict(section))
                for i, (section, vector) in enumerate(zip(sections, vectors))
            ],
        )

    def search(self, project: str, vector: list[float], limit: int) -> list[Section]:
        if not self.client.collection_exists(project):
            return []
        hits = self.client.query_points(project, query=vector, limit=limit).points
        return [Section(**hit.payload) for hit in hits]
