"""Data contracts for WARNY-BI local runtime."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class RagDocument:
    document_id: str
    source_type: str | None
    source_id: str | None
    warning_light_id: str | None
    warning_light_name: str | None
    make: str | None
    model: str | None
    model_year: int | None
    component_category: str | None
    severity: str | None
    recommended_service_type: str | None
    content: str
    source_url: str | None
    image_path: str | None
    review_status: str | None

    def payload(self) -> dict[str, Any]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class SearchResult:
    score: float | None
    document_id: str | None
    source_type: str | None
    source_id: str | None
    warning_light_id: str | None
    warning_light_name: str | None
    make: str | None
    model: str | None
    model_year: int | None
    component_category: str | None
    severity: str | None
    recommended_service_type: str | None
    content: str
    source_url: str | None
    image_path: str | None
    review_status: str | None

    @classmethod
    def from_qdrant_point(cls, point: Any) -> "SearchResult":
        payload = dict(point.payload or {})
        return cls(
            score=getattr(point, "score", None),
            document_id=payload.get("document_id"),
            source_type=payload.get("source_type"),
            source_id=payload.get("source_id"),
            warning_light_id=payload.get("warning_light_id"),
            warning_light_name=payload.get("warning_light_name"),
            make=payload.get("make"),
            model=payload.get("model"),
            model_year=payload.get("model_year"),
            component_category=payload.get("component_category"),
            severity=payload.get("severity"),
            recommended_service_type=payload.get("recommended_service_type"),
            content=str(payload.get("content", "")),
            source_url=payload.get("source_url"),
            image_path=payload.get("image_path"),
            review_status=payload.get("review_status"),
        )

    def is_image(self) -> bool:
        source = (self.source_type or "").lower()
        document_id = (self.document_id or "").lower()
        return document_id.startswith("image:") or "image" in source or "icon" in source or bool(self.image_path)

    def document_prefix(self) -> str | None:
        if not self.document_id:
            return None
        if ":" in self.document_id:
            return self.document_id.split(":", 1)[0]
        if "-" in self.document_id:
            return self.document_id.split("-", 1)[0]
        return None

    def campaign_id(self) -> str | None:
        match = re.search(r"\bCampaign\s+([A-Z0-9]+)\b", self.content, flags=re.IGNORECASE)
        return match.group(1) if match else None

    def source_type_label(self) -> str:
        return self.label(self.source_type or self.document_prefix() or "Evidence")

    def evidence_level(self) -> str:
        prefix = self.document_prefix()
        if prefix == "recall":
            return "recall_candidate_match"
        if prefix == "warning_light":
            return "warning_light_guideline"
        if prefix == "maintenance_service":
            return "service_map_match"
        if prefix == "scenario":
            return "validation_scenario"
        if prefix == "image":
            return "image_icon_support"
        return "retrieved_evidence"

    def evidence_level_label(self) -> str:
        labels = {
            "recall_candidate_match": "Recall candidate",
            "warning_light_guideline": "Warning-light guide",
            "service_map_match": "Service route match",
            "validation_scenario": "Validation scenario",
            "image_icon_support": "Image/icon support",
            "retrieved_evidence": "Retrieved evidence",
        }
        return labels[self.evidence_level()]

    def confidence_label(self) -> str:
        if self.score is None:
            return "Unscored"
        if self.score >= 0.8:
            return "High"
        if self.score >= 0.7:
            return "Medium"
        return "Low"

    def recall_relevance(self) -> str | None:
        return "candidate_match" if self.document_prefix() == "recall" else None

    def recall_relevance_label(self) -> str | None:
        return "Candidate recall match" if self.recall_relevance() else None

    def evidence_text(self) -> str:
        values = {
            "document_id": self.document_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "score": self.score,
            "warning_light_id": self.warning_light_id,
            "warning_light": self.warning_light_name,
            "vehicle": " ".join(str(value) for value in (self.make, self.model, self.model_year) if value is not None),
            "component_category": self.component_category,
            "severity": self.severity,
            "recommended_service_type": self.recommended_service_type,
            "source_url": self.source_url,
            "image_path": self.image_path,
            "review_status": self.review_status,
            "content": self.content,
        }
        return "\n".join(f"{key}: {'' if value is None else value}" for key, value in values.items())

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "document_id": self.document_id,
            "source_type": self.source_type,
            "source_type_label": self.source_type_label(),
            "source_id": self.source_id,
            "rank": None,
            "confidence_label": self.confidence_label(),
            "evidence_level": self.evidence_level(),
            "evidence_level_label": self.evidence_level_label(),
            "warning_light_id": self.warning_light_id,
            "warning_light_name": self.warning_light_name,
            "make": self.make,
            "model": self.model,
            "model_year": self.model_year,
            "campaign_id": self.campaign_id(),
            "recall_relevance": self.recall_relevance(),
            "recall_relevance_label": self.recall_relevance_label(),
            "component_category": self.component_category,
            "severity": self.severity,
            "severity_label": self.label(self.severity) if self.severity else None,
            "recommended_service_type": self.recommended_service_type,
            "recommended_service_label": self.service_label(),
            "source_url": self.source_url,
            "image_path": self.image_path,
            "review_status": self.review_status,
            "content_preview": self.content[:240],
            "rank_score": self.score,
            "match_reasons": [],
        }

    def service_label(self) -> str | None:
        if not self.recommended_service_type:
            return None
        return self.label(self.recommended_service_type)

    def label(self, value: str) -> str:
        replacements = {
            "ENGINE_EMISSIONS_DIAGNOSTIC": "Engine/emissions diagnostic",
            "AIRBAG_SRS_DIAGNOSTIC": "Airbag/SRS diagnostic",
            "TIRE_PRESSURE_AND_TIRE_INSPECTION": "Tire-pressure and tire inspection",
            "SERVICE_SOON_TO_URGENT": "Service soon to urgent",
            "URGENT_OR_IMMEDIATE_STOP": "Stop safely and seek urgent service",
            "URGENT_SERVICE": "Urgent service",
            "SERVICE_SOON": "Service soon",
        }
        if value in replacements:
            return replacements[value]
        if "_" in value or "-" in value or value.isupper():
            return value.replace("_", " ").replace("-", " ").strip().capitalize()
        return value


@dataclass(frozen=True)
class DashboardAnswer:
    payload: dict[str, Any]

    REQUIRED_KEYS = (
        "summary",
        "severity_label",
        "severity_level",
        "severity_color",
        "severity_icon_key",
        "stop_immediately",
        "recommended_service",
        "recall_status",
        "recall_status_level",
        "recall_status_color",
        "recall_icon_key",
        "possible_causes",
        "immediate_action",
        "primary_campaign",
        "recall_interpretation",
        "evidence_used",
        "parsed",
    )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "DashboardAnswer":
        missing = [key for key in cls.REQUIRED_KEYS if key not in payload]
        if missing:
            raise ValueError(f"LLM answer JSON is missing required keys: {', '.join(missing)}")
        if not isinstance(payload["parsed"], dict):
            raise ValueError("LLM answer JSON field 'parsed' must be an object")
        return cls(payload=payload)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class RagResponse:
    query: str
    top_k: int
    include_image_evidence: bool
    answer: DashboardAnswer
    evidence: tuple[SearchResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "top_k": self.top_k,
            "include_image_evidence": self.include_image_evidence,
            "answer": self.answer.to_dict(),
            "evidence": [item.to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class IngestionResult:
    collection: str
    documents_read: int
    documents_indexed: int
    embedding_model: str
    qdrant_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "collection": self.collection,
            "documents_read": self.documents_read,
            "documents_indexed": self.documents_indexed,
            "embedding_model": self.embedding_model,
            "qdrant_url": self.qdrant_url,
        }


@dataclass(frozen=True)
class LoadResult:
    table_name: str
    csv_path: str
    rows_loaded: int
