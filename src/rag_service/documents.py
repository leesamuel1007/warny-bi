"""Document classes shared by WARNY-BI RAG services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RagDocument:
    """One row from the SQL retrieval view."""

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
        return {
            "document_id": self.document_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "warning_light_id": self.warning_light_id,
            "warning_light_name": self.warning_light_name,
            "make": self.make,
            "model": self.model,
            "model_year": self.model_year,
            "component_category": self.component_category,
            "severity": self.severity,
            "recommended_service_type": self.recommended_service_type,
            "content": self.content,
            "source_url": self.source_url,
            "image_path": self.image_path,
            "review_status": self.review_status,
        }


@dataclass(frozen=True)
class SearchResult:
    """One Qdrant search hit converted into a project shape."""

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
    content_preview: str
    rank_score: float | None = None
    match_reasons: tuple[str, ...] = ()

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
            content_preview=str(payload.get("content", ""))[:240],
        )

    def vehicle_text(self) -> str:
        return " ".join(
            str(value)
            for value in (self.make, self.model, self.model_year)
            if value is not None
        )

    def warning_text(self) -> str:
        return " ".join(
            str(value)
            for value in (
                self.warning_light_id,
                self.warning_light_name,
                self.component_category,
                self.recommended_service_type,
            )
            if value is not None
        )

    def source_text(self) -> str:
        return " ".join(
            str(value)
            for value in (self.source_type, self.source_id, self.source_url, self.review_status)
            if value is not None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "document_id": self.document_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "warning_light_id": self.warning_light_id,
            "warning_light_name": self.warning_light_name,
            "make": self.make,
            "model": self.model,
            "model_year": self.model_year,
            "component_category": self.component_category,
            "severity": self.severity,
            "recommended_service_type": self.recommended_service_type,
            "source_url": self.source_url,
            "image_path": self.image_path,
            "review_status": self.review_status,
            "content_preview": self.content_preview,
            "rank_score": self.rank_score,
            "match_reasons": list(self.match_reasons),
        }


@dataclass(frozen=True)
class IngestionResult:
    """Summary returned after a Qdrant ingestion run."""

    collection: str
    documents_read: int
    documents_indexed: int
    embedding_model: str
    qdrant_url: str
    test_query: str | None = None
    test_results: tuple[SearchResult, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "collection": self.collection,
            "documents_read": self.documents_read,
            "documents_indexed": self.documents_indexed,
            "embedding_model": self.embedding_model,
            "qdrant_url": self.qdrant_url,
        }
        if self.test_query:
            payload["test_query"] = self.test_query
            payload["test_results"] = [result.to_dict() for result in self.test_results]
        return payload


@dataclass(frozen=True)
class RagAnswer:
    """Answer and evidence returned by the RAG service."""

    query: str
    answer: str
    evidence: tuple[SearchResult, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer,
            "evidence": [result.to_dict() for result in self.evidence],
        }
