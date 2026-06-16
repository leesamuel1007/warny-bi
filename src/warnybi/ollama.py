"""Ollama HTTP client for embeddings and chat completion."""

from __future__ import annotations

import httpx

from warnybi.config import AnswerSettings, OllamaSettings


class OllamaClient:
    """Calls the local Ollama embedding and chat APIs."""

    def __init__(self, ollama: OllamaSettings, answer: AnswerSettings) -> None:
        self.ollama = ollama
        self.answer = answer

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self.ollama.base_url}/api/embed",
            json={"model": self.ollama.embed_model, "input": texts},
            timeout=self.ollama.timeout_seconds,
        )
        response.raise_for_status()
        embeddings = response.json().get("embeddings")
        if not isinstance(embeddings, list):
            raise ValueError("Ollama embedding response did not include embeddings")
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        embeddings = self.embed_texts([query])
        if not embeddings:
            raise ValueError("Ollama did not return a query embedding")
        return embeddings[0]

    def complete(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.ollama.base_url}/api/chat",
            json={
                "model": self.ollama.chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": self.answer.temperature},
            },
            timeout=self.ollama.timeout_seconds,
        )
        response.raise_for_status()
        message = response.json().get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Ollama chat response did not include message content")
        return content.strip()
