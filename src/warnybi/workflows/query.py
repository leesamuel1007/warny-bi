"""Local FOSS RAG query workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from warnybi.config import RuntimeSettings
from warnybi.models import DashboardAnswer, PromptEvidence, QueryIntent, RagResponse, SearchHit
from warnybi.ollama import OllamaClient
from warnybi.sql import SqlClient
from warnybi.vector import OpenSearchIndex


DEFAULT_TOP_K = 5
MAX_SEARCH_LIMIT = 100


class AnswerPrompt:
    """Renders the structured answer prompt with query and evidence."""

    def __init__(self, settings: RuntimeSettings) -> None:
        prompt_path = settings.root / "config" / "prompts" / "rag_answer_foss.txt"
        if not prompt_path.is_file():
            raise FileNotFoundError(f"FOSS answer prompt not found: {prompt_path}")
        self.template = prompt_path.read_text(encoding="utf-8").strip()

    def render(self, query: str, evidence: tuple[SearchHit, ...]) -> str:
        evidence_text = "\n\n".join(
            f"Evidence [{index + 1}]\n{PromptEvidence(item).text()}" for index, item in enumerate(evidence)
        )
        return self.template.replace("{query}", query).replace("{evidence}", evidence_text)


class IntentPrompt:
    """Renders the query-intent extraction prompt."""

    def __init__(self, settings: RuntimeSettings, vocab_path: Path | None = None) -> None:
        prompt_path = settings.root / "config" / "prompts" / "query_intent_foss.txt"
        if not prompt_path.is_file():
            raise FileNotFoundError(f"query_intent_foss prompt not found: {prompt_path}")
        self.template = prompt_path.read_text(encoding="utf-8").strip()
        self.vocab_text = self.load_vocab(vocab_path or (settings.root / "config" / "canonical_vocab.json"))

    def load_vocab(self, vocab_path: Path) -> str:
        if not vocab_path.is_file():
            return "{}"
        return vocab_path.read_text(encoding="utf-8")

    def render(self, query: str) -> str:
        return self.template.replace("{query}", query).replace("{canonical_vocab}", self.vocab_text)


class LocalRagPipeline:
    """Runs the local FOSS query flow: intent parse, hybrid retrieval, one answer call."""

    def __init__(
        self,
        settings: RuntimeSettings,
        ollama: OllamaClient,
        vector: OpenSearchIndex,
        intent_prompt: IntentPrompt,
        answer_prompt: AnswerPrompt,
        sql: SqlClient,
    ) -> None:
        self.settings = settings
        self.ollama = ollama
        self.vector = vector
        self.intent_prompt = intent_prompt
        self.answer_prompt = answer_prompt
        self.sql = sql

    def answer(self, query: str, top_k: int | None = None, include_image_evidence: bool = False) -> RagResponse:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be blank")

        limit = top_k or DEFAULT_TOP_K
        if limit < 1:
            raise ValueError("top_k must be at least 1")

        intent = self.parse_intent(clean_query)
        search_query = self._build_search_query(clean_query, intent)

        query_vector = self.ollama.embed_query(search_query)
        evidence = self.retrieve_evidence(query_vector, search_query, intent, limit, include_image_evidence)
        answer_text = self.ollama.complete(self.answer_prompt.render(clean_query, evidence))
        answer = DashboardAnswer.from_payload(self._parse_json_object(answer_text))

        response = RagResponse(
            query=clean_query,
            top_k=limit,
            include_image_evidence=include_image_evidence,
            answer=answer,
            evidence=evidence,
        )
        self.sql.insert_query_log(response, self.settings.log_pipeline)
        return response

    def parse_intent(self, query: str) -> QueryIntent:
        raw_text = self.ollama.complete(self.intent_prompt.render(query))
        try:
            return QueryIntent.from_payload(self._parse_json_object(raw_text))
        except ValueError as exc:
            raise ValueError(f"query_intent_foss output is invalid: {exc}") from exc

    def retrieve_evidence(
        self,
        query_vector: list[float],
        query_text: str,
        intent: QueryIntent,
        limit: int,
        include_image_evidence: bool,
    ) -> tuple[SearchHit, ...]:
        search_limit = limit
        results: tuple[SearchHit, ...] = ()

        while search_limit <= MAX_SEARCH_LIMIT:
            results = self.vector.search(query_text, query_vector, intent, search_limit, include_image_evidence)
            if len(results) >= limit:
                break
            if len(results) < search_limit:
                break
            search_limit = min(search_limit * 2, MAX_SEARCH_LIMIT)

        return results[:limit]

    def _build_search_query(self, query: str, intent: QueryIntent) -> str:
        parsed_terms = intent.as_search_text().strip()
        if parsed_terms:
            return f"{query}\n\nParsed profile: {parsed_terms}"
        return query

    def _parse_json_object(self, response_text: str) -> dict[str, Any]:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start < 0 or end < start:
            raise ValueError(f"LLM did not return a JSON object: {response_text}")
        payload = json.loads(response_text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("LLM output JSON must be an object")
        return payload
