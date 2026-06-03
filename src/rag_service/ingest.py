"""Qdrant ingestion orchestration for WARNY-BI."""

from __future__ import annotations

from rag_service.config import IngestionConfig, OllamaConfig, QdrantConfig
from rag_service.db import SqlDocumentReader
from rag_service.documents import IngestionResult, RagDocument
from rag_service.embeddings import OllamaEmbeddingClient
from rag_service.vector_store import QdrantVectorStore


class DocumentBatcher:
    """Splits documents into fixed-size batches."""

    def __init__(self, batch_size: int) -> None:
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        self.batch_size = batch_size

    def batches(self, documents: list[RagDocument]) -> list[list[RagDocument]]:
        return [
            documents[index : index + self.batch_size]
            for index in range(0, len(documents), self.batch_size)
        ]


class QdrantIngestionService:
    """Reads SQL documents, embeds them, and stores them in Qdrant."""

    def __init__(
        self,
        config: IngestionConfig,
        ollama_config: OllamaConfig,
        qdrant_config: QdrantConfig,
        document_reader: SqlDocumentReader,
        embedding_client: OllamaEmbeddingClient,
        vector_store: QdrantVectorStore,
    ) -> None:
        self.config = config
        self.ollama_config = ollama_config
        self.qdrant_config = qdrant_config
        self.document_reader = document_reader
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.batcher = DocumentBatcher(config.batch_size)

    def run(self) -> IngestionResult:
        self.config.validate()
        documents = self.content_documents(self.document_reader.read_documents())
        if not documents:
            raise ValueError(f"No documents with content were read from {self.config.sql_view}")

        first_vector = self.embedding_client.embed_texts([documents[0].content])[0]
        self.vector_store.ensure_collection(vector_size=len(first_vector))
        self.vector_store.upsert_documents([documents[0]], [first_vector])

        indexed_count = 1
        for batch in self.batcher.batches(documents[1:]):
            vectors = self.embedding_client.embed_texts([document.content for document in batch])
            self.vector_store.upsert_documents(batch, vectors)
            indexed_count += len(batch)

        return IngestionResult(
            collection=self.qdrant_config.collection_name,
            documents_read=len(documents),
            documents_indexed=indexed_count,
            embedding_model=self.ollama_config.embedding_model,
            qdrant_url=self.qdrant_config.url,
            test_query=self.config.test_query,
            test_results=self.test_results(),
        )

    def content_documents(self, documents: list[RagDocument]) -> list[RagDocument]:
        return [document for document in documents if document.content.strip()]

    def test_results(self) -> tuple:
        if not self.config.test_query:
            return ()
        query_vector = self.embedding_client.embed_query(self.config.test_query)
        return self.vector_store.search(query_vector, self.config.test_limit)
