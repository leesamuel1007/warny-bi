"""Qdrant vector-index operations for WARNY-BI."""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, Filter, IsNullCondition, PayloadField, PointStruct, VectorParams

from warnybi.config import QdrantSettings
from warnybi.models import RagDocument, SearchResult


class QdrantIndex:
    """Stores and searches WARNY-BI RAG documents in Qdrant."""

    def __init__(self, settings: QdrantSettings) -> None:
        self.settings = settings
        self.client = QdrantClient(url=settings.url)

    def recreate_collection(self, vector_size: int) -> None:
        if self.client.collection_exists(self.settings.collection):
            self.client.delete_collection(self.settings.collection)
        self.create_collection(vector_size)

    def ensure_collection(self, vector_size: int) -> None:
        if not self.client.collection_exists(self.settings.collection):
            self.create_collection(vector_size)

    def create_collection(self, vector_size: int) -> None:
        self.client.create_collection(
            collection_name=self.settings.collection,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    def upsert(self, documents: list[RagDocument], vectors: list[list[float]]) -> None:
        points = [
            PointStruct(
                id=self.point_id(document.document_id),
                vector=vector,
                payload=document.payload(),
            )
            for document, vector in zip(documents, vectors, strict=True)
        ]
        if points:
            self.client.upsert(collection_name=self.settings.collection, points=points)

    def search(self, vector: list[float], limit: int, include_images: bool = True) -> tuple[SearchResult, ...]:
        response = self.client.query_points(
            collection_name=self.settings.collection,
            query=vector,
            query_filter=None if include_images else self.non_image_filter(),
            limit=limit,
            with_payload=True,
        )
        return tuple(SearchResult.from_qdrant_point(point) for point in response.points)

    def non_image_filter(self) -> Filter:
        return Filter(must=[IsNullCondition(is_null=PayloadField(key="image_path"))])

    def point_id(self, document_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"warny-bi:{document_id}"))
