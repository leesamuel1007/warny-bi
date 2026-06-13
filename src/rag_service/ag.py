"""Answer-generation classes for WARNY-BI RAG."""

from __future__ import annotations

import json
from pathlib import Path
import re

import httpx

from rag_service.config import AnswerConfig, OllamaConfig, PromptTemplateConfig
from rag_service.documents import DashboardAnswer, QueryIntentResult, RagAnswer, SearchResult
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


class PromptTemplateReader:
    """Reads validated prompt template files."""

    def __init__(self, template_config: PromptTemplateConfig) -> None:
        self.template_config = template_config
        self.renderer = PromptTemplateRenderer()

    def read(self, template_path: Path) -> str:
        self.template_config.validate()
        return str(template_path.read_text(encoding="utf-8")).strip()

    def render(self, template: str, values: dict[str, object]) -> str:
        return self.renderer.render(template, values)


class PromptTemplateRenderer:
    """Renders named prompt placeholders while preserving literal JSON braces."""

    placeholder_pattern = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

    def render(self, template: str, values: dict[str, object]) -> str:
        missing_names = sorted(
            {
                match.group(1)
                for match in self.placeholder_pattern.finditer(template)
                if match.group(1) not in values
            }
        )
        if missing_names:
            raise ValueError(f"Prompt template has missing values: {', '.join(missing_names)}")

        def replace(match: re.Match[str]) -> str:
            value = values[match.group(1)]
            if value is None:
                return ""
            return str(value)

        return self.placeholder_pattern.sub(replace, template)


class RagPromptBuilder:
    """Builds grounded answer prompts from retrieved evidence."""

    def __init__(self, answer_config: AnswerConfig, template_reader: PromptTemplateReader) -> None:
        self.answer_config = answer_config
        self.template_reader = template_reader
        self.answer_template = self.template_reader.read(self.template_reader.template_config.answer_template_path)
        self.evidence_template = self.template_reader.read(self.template_reader.template_config.evidence_template_path)

    def build(self, query: str, evidence: tuple[SearchResult, ...]) -> str:
        evidence_text = "\n\n".join(self.evidence_block(index + 1, result) for index, result in enumerate(evidence))
        return self.template_reader.render(self.answer_template, {"query": query, "evidence": evidence_text})

    def evidence_block(self, index: int, result: SearchResult) -> str:
        content = result.content[: self.answer_config.max_evidence_chars]
        return self.template_reader.render(
            self.evidence_template,
            {
                "index": index,
                "score": result.score,
                "document_id": self.value_or_empty(result.document_id),
                "source_type": self.value_or_empty(result.source_type),
                "source_id": self.value_or_empty(result.source_id),
                "warning_light_id": self.value_or_empty(result.warning_light_id),
                "warning_light_name": self.value_or_empty(result.warning_light_name),
                "make": self.value_or_empty(result.make),
                "model": self.value_or_empty(result.model),
                "model_year": self.value_or_empty(result.model_year),
                "component_category": self.value_or_empty(result.component_category),
                "severity": self.value_or_empty(result.severity),
                "recommended_service_type": self.value_or_empty(result.recommended_service_type),
                "source_url": self.value_or_empty(result.source_url),
                "image_path": self.value_or_empty(result.image_path),
                "review_status": self.value_or_empty(result.review_status),
                "content": content,
            },
        )

    def value_or_empty(self, value: object) -> object:
        if value is None:
            return ""
        return value


class OllamaQueryIntentExtractor:
    """Extracts structured retrieval intent from a natural-language prompt."""

    def __init__(self, chat_client: OllamaChatClient, template_reader: PromptTemplateReader) -> None:
        self.chat_client = chat_client
        self.template_reader = template_reader
        self.intent_template = self.template_reader.read(self.template_reader.template_config.intent_template_path)

    def extract(self, query: str) -> QueryIntentResult:
        prompt = self.template_reader.render(self.intent_template, {"query": query})
        response_text = self.chat_client.complete(prompt)
        try:
            payload = json.loads(self.json_object_text(response_text))
        except (json.JSONDecodeError, ValueError):
            return QueryIntentResult.empty()
        if not isinstance(payload, dict):
            return QueryIntentResult.empty()
        return QueryIntentResult.from_dict(payload)

    def json_object_text(self, response_text: str) -> str:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start < 0 or end < start:
            raise ValueError(f"Intent extraction did not return a JSON object: {response_text}")
        return response_text[start : end + 1]


class RagDashboardAnswerParser:
    """Parses and normalizes dashboard JSON returned by the answer model."""

    def parse(
        self,
        response_text: str,
        query: str,
        parsed_intent: QueryIntentResult,
        evidence: tuple[SearchResult, ...],
    ) -> DashboardAnswer:
        try:
            payload = json.loads(self.json_object_text(response_text))
        except (json.JSONDecodeError, ValueError):
            payload = {"summary": response_text}
        if not isinstance(payload, dict):
            payload = {"summary": response_text}
        return DashboardAnswer.from_payload(
            payload=payload,
            query=query,
            parsed_intent=parsed_intent,
            evidence=evidence,
            fallback_summary=response_text,
        )

    def json_object_text(self, response_text: str) -> str:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start < 0 or end < start:
            raise ValueError(f"Answer generation did not return a JSON object: {response_text}")
        return response_text[start : end + 1]


class RagAnswerService:
    """Retrieves evidence from Qdrant and generates a grounded answer."""

    def __init__(
        self,
        answer_config: AnswerConfig,
        embedding_client: OllamaEmbeddingClient,
        vector_store: QdrantVectorStore,
        reranker: SearchResultReranker,
        intent_extractor: OllamaQueryIntentExtractor,
        prompt_builder: RagPromptBuilder,
        chat_client: OllamaChatClient,
        answer_parser: RagDashboardAnswerParser | None = None,
    ) -> None:
        self.answer_config = answer_config
        self.embedding_client = embedding_client
        self.vector_store = vector_store
        self.reranker = reranker
        self.intent_extractor = intent_extractor
        self.prompt_builder = prompt_builder
        self.chat_client = chat_client
        self.answer_parser = answer_parser or RagDashboardAnswerParser()

    def answer(
        self,
        query: str,
        top_k: int | None = None,
        include_image_evidence: bool = False,
    ) -> RagAnswer:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be blank")
        parsed_intent = self.intent_extractor.extract(clean_query)
        context = QueryContext(
            query=clean_query,
            make=parsed_intent.make,
            model=parsed_intent.model,
            model_year=parsed_intent.model_year,
            warning_light=parsed_intent.warning_light,
            include_image_evidence=include_image_evidence,
        )
        limit = self.answer_config.validate_top_k(top_k or self.answer_config.default_top_k)
        candidate_limit = self.answer_config.candidate_limit(limit)
        query_vector = self.embedding_client.embed_query(context.search_text())
        candidates = self.vector_store.search(query_vector, candidate_limit)
        evidence = self.reranker.rerank(context, candidates, limit)
        prompt = self.prompt_builder.build(context.search_text(), evidence)
        answer_text = self.chat_client.complete(prompt)
        answer = self.answer_parser.parse(answer_text, clean_query, parsed_intent, evidence)
        return RagAnswer(
            query=clean_query,
            top_k=limit,
            include_image_evidence=include_image_evidence,
            answer=answer,
            evidence=evidence,
            parsed_intent=parsed_intent,
        )
