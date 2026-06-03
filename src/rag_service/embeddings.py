"""Embedding client classes for WARNY-BI RAG services."""

from __future__ import annotations

import httpx

from rag_service.config import OllamaConfig


class OllamaEmbeddingClient:
    """Embeds text with Ollama's local HTTP API."""

    def __init__(self, config: OllamaConfig) -> None:
        self.config = config

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self.config.normalized_base_url()}/api/embed",
            json={"model": self.config.embedding_model, "input": texts},
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise ValueError(f"Ollama response did not include embeddings: {payload}")
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        embeddings = self.embed_texts([query])
        if not embeddings:
            raise ValueError("Ollama did not return an embedding for the query")
        return embeddings[0]
