"""Data contracts for WARNY-BI local runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


@dataclass(frozen=True)
class RagDocument:
    document_id: str
    source_type: str | None
    source_id: str | None
    campaign_id: str | None
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
class QueryIntent:
    make: str | None
    model: str | None
    model_year: int | None
    warning_light: str | None
    warning_light_id: str | None
    component_category: str | None

    REQUIRED_KEYS: tuple[str, ...] = (
        "make",
        "model",
        "model_year",
        "warning_light",
        "warning_light_id",
        "component_category",
    )

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "QueryIntent":
        if not isinstance(payload, dict):
            raise ValueError("query intent must be a JSON object")

        missing = [key for key in cls.REQUIRED_KEYS if key not in payload]
        if missing:
            raise ValueError(f"query intent JSON missing keys: {', '.join(missing)}")

        return cls(
            make=cls._text(payload.get("make")),
            model=cls._text(payload.get("model")),
            model_year=cls._integer(payload.get("model_year")),
            warning_light=cls._text(payload.get("warning_light")),
            warning_light_id=cls._text(payload.get("warning_light_id")),
            component_category=cls._text(payload.get("component_category")),
        )

    def as_search_text(self) -> str:
        pieces = (
            self.make,
            self.model,
            str(self.model_year) if self.model_year is not None else None,
            self.warning_light,
            self.warning_light_id,
            self.component_category,
        )
        return " ".join(piece for piece in pieces if piece).strip()

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped if stripped else None

    @staticmethod
    def _integer(value: Any) -> int | None:
        if value in ("", None, "null"):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class SearchHit:
    score: float | None
    document_id: str | None
    source_type: str | None
    source_id: str | None
    campaign_id: str | None
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
    def from_record(cls, record: dict[str, Any]) -> "SearchHit":
        payload = dict(record)
        return cls(
            score=cls._float(payload.get("_score") or payload.get("score")),
            document_id=cls._text(payload.get("document_id")),
            source_type=cls._text(payload.get("source_type")),
            source_id=cls._text(payload.get("source_id")),
            campaign_id=cls._text(payload.get("campaign_id")),
            warning_light_id=cls._text(payload.get("warning_light_id")),
            warning_light_name=cls._text(payload.get("warning_light_name")),
            make=cls._text(payload.get("make")),
            model=cls._text(payload.get("model")),
            model_year=cls._integer(payload.get("model_year")),
            component_category=cls._text(payload.get("component_category")),
            severity=cls._text(payload.get("severity")),
            recommended_service_type=cls._text(payload.get("recommended_service_type")),
            content=cls._text(payload.get("content")) or "",
            source_url=cls._text(payload.get("source_url")),
            image_path=cls._text(payload.get("image_path")),
            review_status=cls._text(payload.get("review_status")),
        )

    def is_image(self) -> bool:
        source = (self.source_type or "").lower()
        source_id = (self.source_id or "").lower()
        document_id = self.document_id or ""
        return document_id.startswith("image:") or source == "image" or source_id == "image" or bool(self.image_path)

    def document_prefix(self) -> str | None:
        if not self.document_id:
            return None
        if ":" in self.document_id:
            return self.document_id.split(":", 1)[0]
        if "-" in self.document_id:
            return self.document_id.split("-", 1)[0]
        return None

    @staticmethod
    def _text(value: Any) -> str | None:
        if value is None:
            return None
        stripped = str(value).strip()
        return stripped if stripped else None

    @staticmethod
    def _float(value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _integer(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


@dataclass(frozen=True)
class PromptEvidence:
    hit: SearchHit

    def text(self) -> str:
        return (
            f"document_id: {self.hit.document_id}\n"
            f"source_type: {self.hit.source_type}\n"
            f"campaign_id: {self.hit.campaign_id}\n"
            f"score: {self.hit.score}\n"
            f"warning_light_id: {self.hit.warning_light_id}\n"
            f"warning_light: {self.hit.warning_light_name}\n"
            f"vehicle: {self.vehicle_signature()}\n"
            f"component_category: {self.hit.component_category}\n"
            f"severity: {self.hit.severity}\n"
            f"recommended_service_type: {self.hit.recommended_service_type}\n"
            f"source_url: {self.hit.source_url}\n"
            f"image_path: {self.hit.image_path}\n"
            f"review_status: {self.hit.review_status}\n"
            f"content: {self.hit.content}"
        )

    def vehicle_signature(self) -> str:
        return " ".join(
            str(value)
            for value in (self.hit.make, self.hit.model, self.hit.model_year)
            if value is not None
        )


@dataclass(frozen=True)
class EvidenceRow:
    hit: SearchHit

    def campaign_id(self) -> str | None:
        return self.hit.campaign_id

    def evidence_level(self) -> str:
        prefix = self.hit.document_prefix()
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
        if self.hit.score is None:
            return "Unscored"
        if self.hit.score >= 0.8:
            return "High"
        if self.hit.score >= 0.7:
            return "Medium"
        return "Low"

    def recall_relevance(self) -> str | None:
        return "candidate_match" if self.hit.document_prefix() == "recall" else None

    def recall_relevance_label(self) -> str | None:
        return "Candidate recall match" if self.recall_relevance() else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.hit.score,
            "document_id": self.hit.document_id,
            "source_type": self.hit.source_type,
            "source_type_label": self.source_type_label(),
            "source_id": self.hit.source_id,
            "rank": None,
            "confidence_label": self.confidence_label(),
            "evidence_level": self.evidence_level(),
            "evidence_level_label": self.evidence_level_label(),
            "warning_light_id": self.hit.warning_light_id,
            "warning_light_name": self.hit.warning_light_name,
            "make": self.hit.make,
            "model": self.hit.model,
            "model_year": self.hit.model_year,
            "campaign_id": self.campaign_id(),
            "recall_relevance": self.recall_relevance(),
            "recall_relevance_label": self.recall_relevance_label(),
            "component_category": self.hit.component_category,
            "severity": self.hit.severity,
            "severity_label": self.label(self.hit.severity),
            "recommended_service_type": self.hit.recommended_service_type,
            "recommended_service_label": self.label(self.hit.recommended_service_type),
            "source_url": self.hit.source_url,
            "image_path": self.hit.image_path,
            "review_status": self.hit.review_status,
            "content_preview": self.hit.content[:240],
            "rank_score": self.hit.score,
            "match_reasons": [],
        }

    def source_type_label(self) -> str:
        return self.label(self.hit.source_type or self.hit.document_prefix() or "Evidence") or "Evidence"

    def label(self, value: str | None) -> str | None:
        if not value:
            return None
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
        return value.replace("_", " ").replace("-", " ").strip().capitalize()


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
        parsed = payload["parsed"]
        if not isinstance(parsed, dict):
            raise ValueError("LLM answer JSON field 'parsed' must be an object")
        return cls(payload=dict(payload))

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


@dataclass(frozen=True)
class RagResponse:
    query: str
    top_k: int
    include_image_evidence: bool
    answer: DashboardAnswer
    evidence: tuple[SearchHit, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "top_k": self.top_k,
            "include_image_evidence": self.include_image_evidence,
            "answer": self.answer.to_dict(),
            "evidence": [EvidenceRow(item).to_dict() for item in self.evidence],
        }


@dataclass(frozen=True)
class IngestionResult:
    index: str
    documents_read: int
    documents_indexed: int
    embedding_model: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "documents_read": self.documents_read,
            "documents_indexed": self.documents_indexed,
            "embedding_model": self.embedding_model,
        }


@dataclass(frozen=True)
class LoadResult:
    table_name: str
    csv_path: str
    rows_loaded: int


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1)
    include_image_evidence: bool = False
