"""Document classes shared by WARNY-BI RAG services."""

from __future__ import annotations

from dataclasses import dataclass
import re
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

    def source_type_label(self) -> str:
        return self.humanize_label(self.source_type or self.document_prefix() or "Evidence")

    def evidence_level(self) -> str:
        prefix = self.document_prefix()
        reasons = set(self.match_reasons)
        if prefix == "recall":
            if {"make_mismatch", "model_mismatch", "model_year_mismatch"}.intersection(reasons):
                return "recall_candidate_match"
            if {"make", "model", "model_year"}.issubset({reason.split("=", 1)[0] for reason in reasons}):
                return "recall_exact_vehicle_candidate"
            return "recall_candidate_match"
        if prefix == "warning_light":
            return "warning_light_guideline"
        if prefix == "maintenance_service":
            return "service_map_match"
        if prefix == "scenario":
            return "validation_scenario"
        if prefix == "image":
            return "image_icon_support"
        return "generic_retrieved_evidence"

    def evidence_level_label(self) -> str:
        labels = {
            "recall_exact_vehicle_candidate": "Recall candidate: exact make/model/year",
            "recall_candidate_match": "Recall candidate",
            "warning_light_guideline": "Warning-light guide",
            "service_map_match": "Service route match",
            "validation_scenario": "Validation scenario",
            "image_icon_support": "Image/icon support",
            "generic_retrieved_evidence": "Retrieved evidence",
        }
        return labels.get(self.evidence_level(), "Retrieved evidence")

    def confidence_label(self) -> str:
        rank = self.rank_score if self.rank_score is not None else self.score
        if rank is None:
            return "Unscored"
        if rank >= 1.6 or (self.score is not None and self.score >= 0.8):
            return "High"
        if rank >= 1.0 or (self.score is not None and self.score >= 0.7):
            return "Medium"
        return "Low"

    def campaign_id(self) -> str | None:
        match = re.search(r"\bCampaign\s+([A-Z0-9]+)\b", self.content, flags=re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    def recall_relevance(self) -> str | None:
        if self.document_prefix() != "recall":
            return None
        if self.evidence_level() == "recall_exact_vehicle_candidate":
            return "exact_make_model_year_candidate"
        return "candidate_match"

    def recall_relevance_label(self) -> str | None:
        labels = {
            "exact_make_model_year_candidate": "Exact make/model/year candidate",
            "candidate_match": "Candidate recall match",
        }
        relevance = self.recall_relevance()
        if relevance is None:
            return None
        return labels.get(relevance, self.humanize_label(relevance))

    def severity_label(self) -> str | None:
        if self.severity is None:
            return None
        return DashboardAnswer.humanize_service_text(self.severity)

    def recommended_service_label(self) -> str | None:
        if self.recommended_service_type is None:
            return None
        return DashboardAnswer.humanize_service_text(self.recommended_service_type)

    def document_prefix(self) -> str | None:
        if not self.document_id:
            return None
        if ":" in self.document_id:
            return self.document_id.split(":", 1)[0]
        if "-" in self.document_id:
            return self.document_id.split("-", 1)[0]
        return None

    def humanize_label(self, value: str) -> str:
        return value.replace("_", " ").replace("-", " ").strip().title()

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
            "severity_label": self.severity_label(),
            "recommended_service_type": self.recommended_service_type,
            "recommended_service_label": self.recommended_service_label(),
            "source_url": self.source_url,
            "image_path": self.image_path,
            "review_status": self.review_status,
            "content_preview": self.content_preview,
            "rank_score": self.rank_score,
            "match_reasons": list(self.match_reasons),
        }


@dataclass(frozen=True)
class QueryIntentResult:
    """Structured vehicle/warning intent extracted from a natural-language query."""

    make: str | None = None
    model: str | None = None
    model_year: int | None = None
    warning_light: str | None = None

    @classmethod
    def empty(cls) -> "QueryIntentResult":
        return cls()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "QueryIntentResult":
        model_year = payload.get("model_year")
        parsed_year = cls.optional_int(model_year)
        return cls(
            make=cls.optional_text(payload.get("make")),
            model=cls.optional_text(payload.get("model")),
            model_year=parsed_year,
            warning_light=cls.optional_text(payload.get("warning_light")),
        )

    @classmethod
    def optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "null":
            return None
        return text

    @classmethod
    def optional_int(cls, value: Any) -> int | None:
        if value is None:
            return None
        try:
            parsed_value = int(float(str(value).strip()))
        except ValueError:
            return None
        if parsed_value < 1980 or parsed_value > 2039:
            return None
        return parsed_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "make": self.make,
            "model": self.model,
            "model_year": self.model_year,
            "warning_light": self.warning_light,
        }


@dataclass(frozen=True)
class DashboardParsedInfo:
    """Vehicle and warning-light fields surfaced to dashboard visuals."""

    make: str | None = None
    model: str | None = None
    model_year: int | None = None
    warning_light: str | None = None
    warning_light_id: str | None = None
    component_category: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "make": self.make,
            "model": self.model,
            "model_year": self.model_year,
            "warning_light": self.warning_light,
            "warning_light_id": self.warning_light_id,
            "component_category": self.component_category,
        }


@dataclass(frozen=True)
class DashboardAnswer:
    """Structured answer fields intended for Power BI dashboard visuals."""

    summary: str
    severity_label: str
    severity_level: int
    severity_color: str
    severity_icon_key: str
    stop_immediately: bool
    recommended_service: str
    recall_status: str
    recall_status_level: int
    recall_status_color: str
    recall_icon_key: str
    possible_causes: tuple[str, ...]
    immediate_action: str
    primary_campaign: str | None
    recall_interpretation: str
    evidence_used: tuple[str, ...]
    parsed: DashboardParsedInfo

    @classmethod
    def from_payload(
        cls,
        payload: dict[str, Any],
        query: str,
        parsed_intent: QueryIntentResult,
        evidence: tuple[SearchResult, ...],
        fallback_summary: str,
    ) -> "DashboardAnswer":
        answer_payload = payload.get("answer") if isinstance(payload.get("answer"), dict) else payload
        best = cls.best_evidence(evidence)
        recall = cls.best_recall_evidence(evidence)
        parsed_payload = answer_payload.get("parsed") if isinstance(answer_payload.get("parsed"), dict) else {}
        parsed = DashboardParsedInfo(
            make=cls.first_text(parsed_payload.get("make"), parsed_intent.make, best.make if best else None),
            model=cls.first_text(parsed_payload.get("model"), parsed_intent.model, best.model if best else None),
            model_year=cls.first_int(parsed_payload.get("model_year"), parsed_intent.model_year, best.model_year if best else None),
            warning_light=cls.first_text(parsed_payload.get("warning_light"), parsed_intent.warning_light, best.warning_light_name if best else None),
            warning_light_id=cls.first_text(parsed_payload.get("warning_light_id"), best.warning_light_id if best else None),
            component_category=cls.first_text(parsed_payload.get("component_category"), best.component_category if best else None),
        )
        severity_label = cls.humanize_service_text(cls.first_text(
            answer_payload.get("severity_label"),
            best.severity_label() if best else None,
            "Needs review",
        ) or "Needs review")
        severity_level = cls.first_int(answer_payload.get("severity_level"), cls.default_severity_level(severity_label, best.severity if best else None)) or 1
        recall_status = cls.first_text(answer_payload.get("recall_status"), cls.derived_recall_status(recall, parsed)) or "Recall status unavailable"
        recall_status_level = cls.first_int(answer_payload.get("recall_status_level"), cls.recall_level(recall_status, recall)) or 0
        return cls(
            summary=cls.first_text(answer_payload.get("summary"), fallback_summary, query) or query,
            severity_label=severity_label,
            severity_level=severity_level,
            severity_color=cls.first_text(answer_payload.get("severity_color"), cls.default_severity_color(severity_level)) or "#607D8B",
            severity_icon_key=cls.first_text(answer_payload.get("severity_icon_key"), cls.default_severity_icon_key(severity_level)) or "info",
            stop_immediately=cls.first_bool(
                answer_payload.get("stop_immediately"),
                cls.stop_immediately_from_severity(severity_level, best.severity if best else None),
            ),
            recommended_service=cls.humanize_service_text(cls.first_text(
                answer_payload.get("recommended_service"),
                best.recommended_service_label() if best else None,
                "Professional diagnostic inspection",
            ) or "Professional diagnostic inspection"),
            recall_status=recall_status,
            recall_status_level=recall_status_level,
            recall_status_color=cls.first_text(answer_payload.get("recall_status_color"), cls.default_recall_color(recall_status_level)) or "#607D8B",
            recall_icon_key=cls.first_text(answer_payload.get("recall_icon_key"), cls.default_recall_icon_key(recall_status_level)) or "recall_unknown",
            possible_causes=cls.text_tuple(answer_payload.get("possible_causes")),
            immediate_action=cls.first_text(
                answer_payload.get("immediate_action"),
                cls.default_immediate_action(severity_level),
            ) or cls.default_immediate_action(severity_level),
            primary_campaign=cls.first_text(answer_payload.get("primary_campaign"), recall.campaign_id() if recall else None),
            recall_interpretation=cls.first_text(
                answer_payload.get("recall_interpretation"),
                cls.default_recall_interpretation(recall, parsed),
            ) or cls.default_recall_interpretation(recall, parsed),
            evidence_used=cls.evidence_ids(answer_payload.get("evidence_used"), evidence),
            parsed=parsed,
        )

    @classmethod
    def best_evidence(cls, evidence: tuple[SearchResult, ...]) -> SearchResult | None:
        for result in evidence:
            if result.evidence_level() != "image_icon_support":
                return result
        return evidence[0] if evidence else None

    @classmethod
    def best_recall_evidence(cls, evidence: tuple[SearchResult, ...]) -> SearchResult | None:
        for result in evidence:
            if result.document_prefix() == "recall":
                return result
        return None

    @classmethod
    def first_text(cls, *values: Any) -> str | None:
        for value in values:
            if value is None:
                continue
            text = str(value).strip()
            if text and text.lower() != "null":
                return text
        return None

    @classmethod
    def first_int(cls, *values: Any) -> int | None:
        for value in values:
            if value is None:
                continue
            try:
                return int(float(str(value).strip()))
            except ValueError:
                continue
        return None

    @classmethod
    def first_bool(cls, *values: Any) -> bool:
        for value in values:
            if isinstance(value, bool):
                return value
            if value is None:
                continue
            text = str(value).strip().lower()
            if text in {"true", "yes", "1"}:
                return True
            if text in {"false", "no", "0"}:
                return False
        return False

    @classmethod
    def text_tuple(cls, value: Any) -> tuple[str, ...]:
        if isinstance(value, list):
            return tuple(text for item in value if (text := cls.first_text(item)))
        text = cls.first_text(value)
        return (text,) if text else ()

    @classmethod
    def evidence_ids(cls, value: Any, evidence: tuple[SearchResult, ...]) -> tuple[str, ...]:
        ids = cls.text_tuple(value)
        if ids:
            return ids
        return tuple(result.document_id for result in evidence if result.document_id)

    @classmethod
    def default_severity_level(cls, label: str | None, raw_severity: str | None) -> int:
        text = f"{label or ''} {raw_severity or ''}".lower()
        if "immediate" in text or "stop" in text:
            return 4
        if "urgent" in text:
            return 3
        if "soon" in text or "service" in text:
            return 2
        return 1

    @classmethod
    def default_severity_color(cls, level: int) -> str:
        return {
            4: "#D32F2F",
            3: "#E67E22",
            2: "#F2C94C",
            1: "#607D8B",
        }.get(level, "#607D8B")

    @classmethod
    def default_severity_icon_key(cls, level: int) -> str:
        return {
            4: "stop",
            3: "warning",
            2: "service_soon",
            1: "info",
        }.get(level, "info")

    @classmethod
    def stop_immediately_from_severity(cls, level: int, raw_severity: str | None) -> bool:
        return level >= 4 or "IMMEDIATE_STOP" in str(raw_severity or "")

    @classmethod
    def recall_level(cls, status: str, recall: SearchResult | None) -> int:
        text = status.lower()
        if recall and recall.evidence_level() == "recall_exact_vehicle_candidate":
            return 3
        if "candidate" in text or "match" in text:
            return 3
        if "possible" in text or "needs" in text or "cannot" in text:
            return 2
        if "no" in text:
            return 1
        return 0

    @classmethod
    def default_recall_color(cls, level: int) -> str:
        return {
            3: "#7B1FA2",
            2: "#1976D2",
            1: "#2E7D32",
            0: "#607D8B",
        }.get(level, "#607D8B")

    @classmethod
    def default_recall_icon_key(cls, level: int) -> str:
        return {
            3: "recall_candidate",
            2: "recall_review",
            1: "recall_none",
            0: "recall_unknown",
        }.get(level, "recall_unknown")

    @classmethod
    def derived_recall_status(cls, recall: SearchResult | None, parsed: DashboardParsedInfo) -> str:
        if recall is None:
            if parsed.make and parsed.model and parsed.model_year:
                return "No recall candidate in retrieved evidence"
            return "Recall applicability needs exact vehicle details"
        if recall.evidence_level() == "recall_exact_vehicle_candidate":
            return "Candidate recall match for exact make/model/year"
        return "Candidate recall match"

    @classmethod
    def default_immediate_action(cls, severity_level: int) -> str:
        if severity_level >= 4:
            return "Stop safely and seek urgent professional service."
        if severity_level >= 3:
            return "Arrange prompt diagnostic service; stop safely if the light flashes or the vehicle feels unsafe."
        return "Review the owner manual and schedule service if the warning remains on."

    @classmethod
    def default_recall_interpretation(cls, recall: SearchResult | None, parsed: DashboardParsedInfo) -> str:
        if recall is None:
            return "No recall candidate was retrieved. Exact recall applicability still requires make, model, model year, and VIN lookup."
        vehicle = " ".join(str(value) for value in (parsed.make, parsed.model, parsed.model_year) if value)
        campaign = recall.campaign_id()
        campaign_text = f" Campaign {campaign}" if campaign else ""
        return f"A recall candidate was retrieved for {vehicle or 'the described vehicle'}.{campaign_text} VIN confirmation is required before treating it as applicable."

    @classmethod
    def humanize_service_text(cls, value: str) -> str:
        text = value.strip()
        if not text:
            return text
        replacements = {
            "URGENT_OR_IMMEDIATE_STOP": "Stop safely and seek urgent service",
            "SERVICE_SOON_TO_URGENT": "Service soon; urgent if symptoms are severe",
            "URGENT_SERVICE": "Urgent service",
            "SERVICE_SOON": "Service soon",
            "ENGINE_EMISSIONS_DIAGNOSTIC": "Engine/emissions diagnostic",
            "AIRBAG_SRS_DIAGNOSTIC": "Airbag/SRS diagnostic",
            "TIRE_PRESSURE_AND_TIRE_INSPECTION": "Tire-pressure and tire inspection",
        }
        if text in replacements:
            return replacements[text]
        if "_" not in text and "-" not in text and not text.isupper():
            return text
        return text.replace("_", " ").replace("-", " ").strip().capitalize()

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": self.summary,
            "severity_label": self.severity_label,
            "severity_level": self.severity_level,
            "severity_color": self.severity_color,
            "severity_icon_key": self.severity_icon_key,
            "stop_immediately": self.stop_immediately,
            "recommended_service": self.recommended_service,
            "recall_status": self.recall_status,
            "recall_status_level": self.recall_status_level,
            "recall_status_color": self.recall_status_color,
            "recall_icon_key": self.recall_icon_key,
            "possible_causes": list(self.possible_causes),
            "immediate_action": self.immediate_action,
            "primary_campaign": self.primary_campaign,
            "recall_interpretation": self.recall_interpretation,
            "evidence_used": list(self.evidence_used),
            "parsed": self.parsed.to_dict(),
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
    answer: DashboardAnswer
    evidence: tuple[SearchResult, ...]
    parsed_intent: QueryIntentResult

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "answer": self.answer.to_dict(),
            "evidence": [result.to_dict() for result in self.evidence],
        }
