"""FastAPI app classes for WARNY-BI RAG."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from rag_service.ag import RagAnswerService


class QueryRequest(BaseModel):
    """Request body for text RAG queries."""

    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    make: str | None = None
    model: str | None = None
    model_year: int | None = Field(default=None, ge=1980, le=2039)
    warning_light: str | None = None
    include_image_evidence: bool = False


class EvidenceResponse(BaseModel):
    """One evidence row returned to API clients."""

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
    source_url: str | None
    image_path: str | None
    review_status: str | None
    content_preview: str
    rank_score: float | None
    match_reasons: list[str]


class QueryResponse(BaseModel):
    """Response body for text RAG queries."""

    query: str
    answer: str
    evidence: list[EvidenceResponse]


class HealthResponse(BaseModel):
    """Response body for health checks."""

    status: str
    service: str


class WarnyBiApi:
    """Owns FastAPI app construction and route registration."""

    def __init__(self, answer_service: RagAnswerService) -> None:
        self.answer_service = answer_service
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
                make=request.make,
                model=request.model,
                model_year=request.model_year,
                warning_light=request.warning_light,
                include_image_evidence=request.include_image_evidence,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
        return QueryResponse(
            query=result.query,
            answer=result.answer,
            evidence=[
                EvidenceResponse(**self.evidence_payload(evidence))
                for evidence in result.evidence
            ],
        )

    def evidence_payload(self, evidence: Any) -> dict[str, Any]:
        return evidence.to_dict()
