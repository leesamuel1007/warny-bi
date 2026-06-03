"""Answer-generation classes for WARNY-BI RAG."""

from __future__ import annotations

from pathlib import Path

import httpx

from rag_service.config import AnswerConfig, OllamaConfig, PromptTemplateConfig
from rag_service.documents import RagAnswer, SearchResult
from rag_service.embeddings import OllamaEmbeddingClient
from rag_service.retrieval import QueryContext, SearchResultReranker
from rag_service.vector_store import QdrantVectorStore


class OllamaChatClient:
    """Calls Ollama chat models."""

    def __init__(self, ollama_config: OllamaConfig, answer_config: AnswerConfig) -> None:
        self.ollama_config = ollama_config
        self.answer_config = answer_config

    def complete(self, prompt: str) -> str:
        response = httpx.post(
            f"{self.ollama_config.normalized_base_url()}/api/chat",
            json={
                "model": self.ollama_config.chat_model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": self.answer_config.temperature},
            },
            timeout=self.ollama_config.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        message = payload.get("message", {})
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ValueError(f"Ollama response did not include message content: {payload}")
        return content.strip()


class RagPromptBuilder:
    """Builds grounded answer prompts from retrieved evidence."""

    def __init__(self, answer_config: AnswerConfig, template_config: PromptTemplateConfig) -> None:
        self.answer_config = answer_config
        self.template_config = template_config
        self.answer_template = self.read_template(self.template_config.answer_template_path)
        self.evidence_template = self.read_template(self.template_config.evidence_template_path)

    def read_template(self, template_path: Path) -> str:
        self.template_config.validate()
        return str(template_path.read_text(encoding="utf-8")).strip()

    def build(self, query: str, evidence: tuple[SearchResult, ...]) -> str:
        evidence_text = "\n\n".join(self.evidence_block(index + 1, result) for index, result in enumerate(evidence))
        return self.answer_template.format(query=query, evidence=evidence_text)

    def evidence_block(self, index: int, result: SearchResult) -> str:
        content = result.content[: self.answer_config.max_evidence_chars]
        return self.evidence_template.format(
            index=index,
            score=result.score,
            document_id=self.value_or_empty(result.document_id),
            source_type=self.value_or_empty(result.source_type),
            source_id=self.value_or_empty(result.source_id),
            warning_light_id=self.value_or_empty(result.warning_light_id),
            warning_light_name=self.value_or_empty(result.warning_light_name),
            make=self.value_or_empty(result.make),
            model=self.value_or_empty(result.model),
            model_year=self.value_or_empty(result.model_year),
            component_category=self.value_or_empty(result.component_category),
            severity=self.value_or_empty(result.severity),
            recommended_service_type=self.value_or_empty(result.recommended_service_type),
            source_url=self.value_or_empty(result.source_url),
            image_path=self.value_or_empty(result.image_path),
            review_status=self.value_or_empty(result.review_status),
            content=content,
        )

    def value_or_empty(self, value: object) -> object:
        if value is None:
            return ""
        return value


class RagAnswerService:
    """Retrieves evidence from Qdrant and generates a grounded answer."""

    def __init__(
        self,
        answer_config: AnswerConfig,
        embedding_client: OllamaEmbeddingClient,
        vector_store: QdrantVectorStore,
        reranker: SearchResultReranker,
        prompt_builder: RagPromptBuilder,
        chat_client: OllamaChatClient,
    ) -> None:
        self.answer_config = answer_config
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.reranker = reranker
        self.prompt_builder = prompt_builder
        self.chat_client = chat_client

    def answer(
        self,
        query: str,
        top_k: int | None = None,
        make: str | None = None,
        model: str | None = None,
        model_year: int | None = None,
        warning_light: str | None = None,
        include_image_evidence: bool = False,
    ) -> RagAnswer:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be blank")
        context = QueryContext(
            query=clean_query,
            make=make,
            model=model,
            model_year=model_year,
            warning_light=warning_light,
            include_image_evidence=include_image_evidence,
        )
        limit = self.answer_config.validate_top_k(top_k or self.answer_config.default_top_k)
        candidate_limit = self.answer_config.candidate_limit(limit)
        query_vector = self.embedding_client.embed_query(context.search_text())
        candidates = self.vector_store.search(query_vector, candidate_limit)
        evidence = self.reranker.rerank(context, candidates, limit)
        prompt = self.prompt_builder.build(context.search_text(), evidence)
        answer_text = self.chat_client.complete(prompt)
        return RagAnswer(query=clean_query, answer=answer_text, evidence=evidence)
