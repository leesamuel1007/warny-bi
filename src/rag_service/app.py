"""FastAPI app classes for WARNY-BI RAG."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_service.ag import RagAnswerService
from rag_service.query_log import NullQueryLogger, QueryLogger


class QueryRequest(BaseModel):
    """Request body for text RAG queries."""

    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    include_image_evidence: bool = False


class ParsedAnswerResponse(BaseModel):
    """Parsed vehicle and warning-light fields for dashboard visuals."""

    make: str | None
    model: str | None
    model_year: int | None
    warning_light: str | None
    warning_light_id: str | None
    component_category: str | None


class AnswerResponse(BaseModel):
    """Structured answer fields returned to Power BI."""

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
    possible_causes: list[str]
    immediate_action: str
    primary_campaign: str | None
    recall_interpretation: str
    evidence_used: list[str]
    parsed: ParsedAnswerResponse


class EvidenceResponse(BaseModel):
    """One evidence row returned to API clients."""

    score: float | None
    document_id: str | None
    source_type: str | None
    source_type_label: str
    source_id: str | None
    rank: int | None
    confidence_label: str
    evidence_level: str
    evidence_level_label: str
    warning_light_id: str | None
    warning_light_name: str | None
    make: str | None
    model: str | None
    model_year: int | None
    campaign_id: str | None
    recall_relevance: str | None
    recall_relevance_label: str | None
    component_category: str | None
    severity: str | None
    severity_label: str | None
    recommended_service_type: str | None
    recommended_service_label: str | None
    source_url: str | None
    image_path: str | None
    review_status: str | None
    content_preview: str
    rank_score: float | None
    match_reasons: list[str]


class QueryResponse(BaseModel):
    """Response body for text RAG queries."""

    query: str
    answer: AnswerResponse
    evidence: list[EvidenceResponse]


class HealthResponse(BaseModel):
    """Response body for health checks."""

    status: str
    service: str


class WarnyBiApi:
    """Owns FastAPI app construction and route registration."""

    def __init__(self, answer_service: RagAnswerService, query_logger: QueryLogger | None = None) -> None:
        self.answer_service = answer_service
        self.query_logger = query_logger or NullQueryLogger()
        self.app = FastAPI(title="WARNY-BI RAG API", version="0.1.0")
        self.register_routes()

    def register_routes(self) -> None:
        self.app.get("/health", response_model=HealthResponse)(self.health)
        self.app.post("/query", response_model=QueryResponse)(self.query)

    def health(self) -> HealthResponse:
        return HealthResponse(status="ok", service="warny-bi-rag")

    def query(self, request: QueryRequest) -> QueryResponse:
        try:
            result = self.answer_service.answer(
                query=request.query,
                top_k=request.top_k,
                include_image_evidence=request.include_image_evidence,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
        try:
            self.query_logger.log(result)
        except Exception:
            pass
        return QueryResponse(
            query=result.query,
            answer=AnswerResponse(**result.answer.to_dict()),
            evidence=[
                EvidenceResponse(**self.evidence_payload(evidence))
                for evidence in result.evidence
            ],
        )

    def evidence_payload(self, evidence: Any) -> dict[str, Any]:
        return evidence.to_dict()
