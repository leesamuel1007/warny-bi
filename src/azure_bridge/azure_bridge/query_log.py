"""Query-log rows for Azure SQL output bindings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class QueryLogRows:
    """Rows that should be written to Azure SQL."""

    query_row: dict[str, Any]
    evidence_rows: list[dict[str, Any]]


class QueryLogRowBuilder:
    """Builds Azure SQL rows from a normalized bridge response."""

    def __init__(self, pipeline: str) -> None:
        self.pipeline = pipeline

    def build(self, response: dict[str, Any]) -> QueryLogRows:
        query_id = str(uuid4())
        evidence = self.evidence_list(response)
        query_row = self.query_row(query_id, response, evidence)
        evidence_rows = [
            self.evidence_row(query_id, rank, evidence_row)
            for rank, evidence_row in enumerate(evidence, start=1)
        ]
        return QueryLogRows(query_row=query_row, evidence_rows=evidence_rows)

    def query_row(
        self,
        query_id: str,
        response: dict[str, Any],
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any]:
        answer = self.record(response.get("answer"))
        parsed = self.record(answer.get("parsed"))
        top = evidence[0] if evidence else {}
        return {
            "query_id": query_id,
            "pipeline": self.pipeline,
            "user_prompt": self.text(response.get("query")),
            "answer_summary": self.text(answer.get("summary")),
            "parsed_make": self.text(parsed.get("make")),
            "parsed_model": self.text(parsed.get("model")),
            "parsed_model_year": self.integer(parsed.get("model_year")),
            "parsed_warning_light": self.text(parsed.get("warning_light")),
            "warning_light_id": self.text(parsed.get("warning_light_id")),
            "component_category": self.text(parsed.get("component_category")),
            "severity": self.text(answer.get("severity_label")),
            "severity_level": self.integer(answer.get("severity_level")),
            "stop_immediately": self.boolean(answer.get("stop_immediately")),
            "recommended_service": self.text(answer.get("recommended_service")),
            "recall_status": self.text(answer.get("recall_status")),
            "recall_status_level": self.integer(answer.get("recall_status_level")),
            "primary_campaign": self.text(answer.get("primary_campaign")),
            "recall_interpretation": self.text(answer.get("recall_interpretation")),
            "evidence_count": len(evidence),
            "recall_candidate_count": self.count_documents(evidence, "recall:"),
            "warning_guide_count": self.count_evidence_level(evidence, "warning_light_guideline"),
            "service_map_count": self.count_evidence_level(evidence, "service_map_match"),
            "validation_scenario_count": self.count_evidence_level(evidence, "validation_scenario"),
            "image_support_count": self.count_evidence_level(evidence, "image_icon_support"),
            "top_document_id": self.text(top.get("document_id")),
            "top_source_type": self.text(top.get("source_type")),
            "top_confidence_label": self.text(top.get("confidence_label")),
            "top_rank_score": self.float_or_none(top.get("rank_score")),
            "top_score": self.float_or_none(top.get("score")),
        }

    def evidence_row(self, query_id: str, rank: int, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "query_id": query_id,
            "evidence_rank": self.integer(row.get("rank")) or rank,
            "document_id": self.text(row.get("document_id")),
            "source_type": self.text(row.get("source_type")),
            "source_type_label": self.text(row.get("source_type_label")),
            "source_id": self.text(row.get("source_id")),
            "confidence_label": self.text(row.get("confidence_label")),
            "evidence_level": self.text(row.get("evidence_level")),
            "evidence_level_label": self.text(row.get("evidence_level_label")),
            "warning_light_id": self.text(row.get("warning_light_id")),
            "warning_light_name": self.text(row.get("warning_light_name")),
            "make": self.text(row.get("make")),
            "model": self.text(row.get("model")),
            "model_year": self.integer(row.get("model_year")),
            "campaign_id": self.text(row.get("campaign_id")),
            "recall_relevance": self.text(row.get("recall_relevance")),
            "recall_relevance_label": self.text(row.get("recall_relevance_label")),
            "component_category": self.text(row.get("component_category")),
            "severity": self.text(row.get("severity")),
            "severity_label": self.text(row.get("severity_label")),
            "recommended_service_type": self.text(row.get("recommended_service_type")),
            "recommended_service_label": self.text(row.get("recommended_service_label")),
            "source_url": self.text(row.get("source_url")),
            "content_preview": self.text(row.get("content_preview")),
            "rank_score": self.float_or_none(row.get("rank_score")),
            "score": self.float_or_none(row.get("score")),
        }

    def evidence_list(self, response: dict[str, Any]) -> list[dict[str, Any]]:
        evidence = response.get("evidence")
        if not isinstance(evidence, list):
            return []
        return [row for row in evidence if isinstance(row, dict)]

    def count_documents(self, evidence: list[dict[str, Any]], prefix: str) -> int:
        return sum(1 for row in evidence if str(row.get("document_id") or "").startswith(prefix))

    def count_evidence_level(self, evidence: list[dict[str, Any]], evidence_level: str) -> int:
        return sum(1 for row in evidence if row.get("evidence_level") == evidence_level)

    def record(self, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    def text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def integer(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(float(str(value).strip()))
        except ValueError:
            return None

    def float_or_none(self, value: Any) -> float | None:
        if value is None:
            return None
        try:
            return float(str(value).strip())
        except ValueError:
            return None

    def boolean(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"}:
            return False
        return None
