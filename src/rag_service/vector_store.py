"""Qdrant vector-store classes for WARNY-BI RAG services."""

from __future__ import annotations

from typing import Any
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from rag_service.config import QdrantConfig
from rag_service.documents import RagDocument, SearchResult


class QdrantVectorStore:
    """Manages WARNY-BI documents in Qdrant."""

    def __init__(self, config: QdrantConfig) -> None:
        self.config = config
        self.client = QdrantClient(url=config.url)

    def ensure_collection(self, vector_size: int) -> None:
        exists = self.client.collection_exists(self.config.collection_name)
        if exists and self.config.recreate:
            self.client.delete_collection(self.config.collection_name)
            exists = False
        if not exists:
            self.client.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def upsert_documents(self, documents: list[RagDocument], vectors: list[list[float]]) -> None:
        points = [
            PointStruct(
                id=self.stable_point_id(document.document_id),
                vector=vector,
                payload=document.payload(),
            )
            for document, vector in zip(documents, vectors, strict=True)
        ]
        if points:
            self.client.upsert(collection_name=self.config.collection_name, points=points)

    def search(self, vector: list[float], limit: int) -> tuple[SearchResult, ...]:
        response = self.client.query_points(
            collection_name=self.config.collection_name,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return tuple(SearchResult.from_qdrant_point(point) for point in response.points)

    def stable_point_id(self, document_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"warny-bi:{document_id}"))
