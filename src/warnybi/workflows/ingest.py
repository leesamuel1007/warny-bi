"""OpenSearch ingestion workflow."""

from __future__ import annotations

import argparse
import json

from warnybi.config import RuntimeSettings
from warnybi.models import IngestionResult, RagDocument
from warnybi.ollama import OllamaClient
from warnybi.sql import SqlClient
from warnybi.vector import OpenSearchIndex
from warnybi.workflows.factory import RuntimeFactory


class IngestionPipeline:
    """Loads SQL retrieval documents into OpenSearch."""

    def __init__(self, settings: RuntimeSettings, sql: SqlClient, ollama: OllamaClient, vector: OpenSearchIndex) -> None:
        self.settings = settings
        self.sql = sql
        self.ollama = ollama
        self.vector = vector

    def run(self, recreate: bool) -> IngestionResult:
        documents = [document for document in self.sql.read_documents(self.settings.sql_view) if document.content.strip()]
        if not documents:
            raise ValueError(f"No documents with content were read from {self.settings.sql_view}")

        first_batch = documents[: self.settings.embed_batch_size]
        first_vectors = self.ollama.embed_texts([document.content for document in first_batch])
        if not first_vectors:
            raise ValueError("Embedding service did not return vectors")

        vector_length = len(first_vectors[0])
        if recreate:
            self.vector.recreate_index(vector_length)
        else:
            self.vector.ensure_index(vector_length)

        indexed = self._index_batch(first_batch, first_vectors)
        for batch in self._batched(documents[len(first_batch) :]):
            vectors = self.ollama.embed_texts([document.content for document in batch])
            if vectors:
                indexed += self._index_batch(batch, vectors)

        return IngestionResult(
            index=self.settings.opensearch.index,
            documents_read=len(documents),
            documents_indexed=indexed,
            embedding_model=self.settings.ollama.embed_model,
        )

    def _index_batch(self, documents: list[RagDocument], vectors: list[list[float]]) -> int:
        self.vector.upsert_documents(documents, vectors)
        return len(documents)

    def _batched(self, documents: list[RagDocument]) -> list[list[RagDocument]]:
        size = self.settings.embed_batch_size
        if size < 1:
            raise ValueError("EMBED_BATCH_SIZE must be at least 1")
        return [documents[index : index + size] for index in range(0, len(documents), size)]


class OpenSearchIngestCli:
    """CLI for SQL retrieval view to OpenSearch indexing."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Load dbo.vw_rag_documents into OpenSearch")
        parser.add_argument("--recreate", action="store_true", help="Delete and recreate the OpenSearch index")
        args = parser.parse_args()

        result = RuntimeFactory().ingestion().run(recreate=args.recreate)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0
