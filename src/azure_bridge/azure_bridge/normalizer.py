"""Normalize Azure OpenAI responses into the WARNY-BI response contract."""

from __future__ import annotations

import json
import re
from typing import Any


class EmptyAnswerFactory:
    """Creates the empty dashboard answer used when no prompt is supplied."""

    def create(self) -> dict[str, Any]:
        return {
            "summary": "",
            "severity_label": "",
            "severity_level": None,
            "severity_color": "#607D8B",
            "severity_icon_key": "info",
            "stop_immediately": False,
            "recommended_service": "",
            "recall_status": "",
            "recall_status_level": None,
            "recall_status_color": "#607D8B",
            "recall_icon_key": "recall_unknown",
            "possible_causes": [],
            "immediate_action": "",
            "primary_campaign": None,
            "recall_interpretation": "",
            "evidence_used": [],
            "parsed": {
                "make": None,
                "model": None,
                "model_year": None,
                "warning_light": None,
                "warning_light_id": None,
                "component_category": None,
            },
        }


class AzureRagResponseNormalizer:
    """Converts Azure OpenAI chat-completion payloads into Power BI records."""

    def __init__(self, empty_answer_factory: EmptyAnswerFactory | None = None) -> None:
        self.empty_answer_factory = empty_answer_factory or EmptyAnswerFactory()

    def empty_response(self, query: str = "") -> dict[str, Any]:
        return {
            "query": query,
            "answer": self.empty_answer_factory.create(),
            "evidence": [],
            "raw": None,
        }

    def normalize(self, query: str, payload: dict[str, Any]) -> dict[str, Any]:
        message = self.message(payload)
        content = str(message.get("content") or "")
        context = message.get("context") if isinstance(message.get("context"), dict) else {}
        citations = context.get("citations") if isinstance(context.get("citations"), list) else []
        evidence = [
            self.normalize_citation(citation, index + 1)
            for index, citation in enumerate(citations)
            if isinstance(citation, dict)
        ]
        return {
            "query": query,
            "answer": self.parse_answer(content),
            "evidence": evidence,
            "raw": payload,
        }

    def message(self, payload: dict[str, Any]) -> dict[str, Any]:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return {}
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            return {}
        message = first_choice.get("message")
        return message if isinstance(message, dict) else {}

    def parse_answer(self, content: str) -> dict[str, Any]:
        parsed = self.try_json_object(content)
        if isinstance(parsed, dict):
            answer = parsed.get("answer") if isinstance(parsed.get("answer"), dict) else parsed
            return self.merge_answer_defaults(answer)
        answer = self.empty_answer_factory.create()
        answer["summary"] = content
        return answer

    def try_json_object(self, content: str) -> dict[str, Any] | None:
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            start = content.find("{")
            end = content.rfind("}")
            if start < 0 or end < start:
                return None
            try:
                value = json.loads(content[start : end + 1])
            except json.JSONDecodeError:
                return None
        return value if isinstance(value, dict) else None

    def merge_answer_defaults(self, answer: dict[str, Any]) -> dict[str, Any]:
        defaults = self.empty_answer_factory.create()
        merged = {**defaults, **answer}
        parsed = answer.get("parsed") if isinstance(answer.get("parsed"), dict) else {}
        merged["parsed"] = {**defaults["parsed"], **parsed}
        return merged

    def normalize_citation(self, citation: dict[str, Any], rank: int) -> dict[str, Any]:
        content = self.text_or_empty(citation.get("content"))
        document_id = self.canonical_document_id(
            self.first_text(
                citation.get("chunk_id"),
                citation.get("filepath"),
                citation.get("title"),
                f"azure-citation-{rank}",
            )
        )
        source_type = self.source_type(document_id)
        evidence_level = self.evidence_level(document_id)
        return {
            "score": None,
            "document_id": document_id,
            "source_type": source_type,
            "source_type_label": self.label(source_type),
            "source_id": self.source_id(document_id),
            "rank": rank,
            "confidence_label": "Unscored",
            "evidence_level": evidence_level,
            "evidence_level_label": self.label(evidence_level),
            "warning_light_id": None,
            "warning_light_name": None,
            "make": None,
            "model": None,
            "model_year": None,
            "campaign_id": self.campaign_id(content),
            "recall_relevance": "candidate_match" if document_id.startswith("recall:") else None,
            "recall_relevance_label": "Candidate recall match" if document_id.startswith("recall:") else None,
            "component_category": None,
            "severity": None,
            "severity_label": None,
            "recommended_service_type": None,
            "recommended_service_label": None,
            "source_url": self.first_text(citation.get("url")),
            "image_path": None,
            "review_status": None,
            "content_preview": content[:240],
            "rank_score": None,
            "match_reasons": [],
        }

    def canonical_document_id(self, value: str | None) -> str:
        if value is None:
            return "azure-citation"
        before_pages = value.split("_pages", 1)[0]
        parts = before_pages.split("_")
        token = "_".join(parts[1:]) if len(parts) > 1 else before_pages
        mappings = {
            "recall-": "recall:",
            "warning_light-": "warning_light:",
            "maintenance_service-": "maintenance_service:",
            "image-": "image:",
            "scenario-": "scenario:",
        }
        for prefix, canonical_prefix in mappings.items():
            if token.startswith(prefix):
                return canonical_prefix + token.removeprefix(prefix)
        return token

    def source_type(self, document_id: str) -> str:
        if document_id.startswith("recall:"):
            return "NHTSA_RECALLS_API"
        if document_id.startswith("warning_light:"):
            return "STANDARD_64_WARNING_LIGHT_GUIDE_PLUS_OEM_REFERENCE"
        if document_id.startswith("maintenance_service:"):
            return "TEAM_STRUCTURED_SERVICE_MAP_FROM_STANDARD_64_WARNING_CATALOG"
        if document_id.startswith("image:"):
            return "WARNING_LIGHT_IMAGE_METADATA"
        if document_id.startswith("scenario:"):
            return "STANDARD_64_WARNING_LIGHT_PLUS_NHTSA_RECALL"
        return "AZURE_AI_SEARCH"

    def evidence_level(self, document_id: str) -> str:
        if document_id.startswith("recall:"):
            return "recall_candidate_match"
        if document_id.startswith("warning_light:"):
            return "warning_light_guideline"
        if document_id.startswith("maintenance_service:"):
            return "service_map_match"
        if document_id.startswith("scenario:"):
            return "validation_scenario"
        if document_id.startswith("image:"):
            return "image_icon_support"
        return "generic_retrieved_evidence"

    def source_id(self, document_id: str) -> str:
        if ":" not in document_id:
            return document_id
        return document_id.split(":", 1)[1]

    def campaign_id(self, content: str) -> str | None:
        match = re.search(r"\bCampaign\s+([A-Z0-9]+)\b", content, flags=re.IGNORECASE)
        return match.group(1) if match else None

    def label(self, value: str | None) -> str | None:
        if value is None:
            return None
        return value.replace("_", " ").replace("-", " ").strip().title()

    def first_text(self, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() != "null":
                return text
        return None

    def text_or_empty(self, value: Any) -> str:
        text = self.first_text(value)
        return text or ""
