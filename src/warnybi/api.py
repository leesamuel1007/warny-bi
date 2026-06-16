"""FastAPI boundary for the WARNY-BI local runtime."""

from __future__ import annotations

import logging
import time
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from warnybi.config import RuntimeSettings


LOGGER = logging.getLogger(__name__)


class QueryRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = Field(default=None, ge=1, le=20)
    include_image_evidence: bool = False


class ApiServer:
    """Owns FastAPI route registration for the local RAG service."""

    def __init__(self, pipeline: Any, settings: RuntimeSettings) -> None:
        self.pipeline = pipeline
        self.retry = Retry(settings)
        self.app = FastAPI(title="WARNY-BI RAG API", version="0.1.0")
        self.app.get("/health")(self.health)
        self.app.post("/query")(self.query)

    def health(self) -> dict[str, str]:
        return {"status": "ok", "service": "warny-bi-rag"}

    def query(self, request: QueryRequest) -> dict:
        try:
            response = self.retry.run(
                "RAG query",
                lambda: self.pipeline.answer(request.query, request.top_k, request.include_image_evidence),
            )
        except ValueError as error:
            LOGGER.warning("Rejected query request: %s", error)
            raise HTTPException(status_code=400, detail=str(error)) from error
        except Exception as error:
            LOGGER.exception("RAG query failed")
            raise HTTPException(status_code=500, detail=str(error)) from error
        return response.to_dict()


class Retry:
    """Retries recoverable local backend operations."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings

    def run(self, operation_name: str, operation: Any) -> Any:
        last_error: Exception | None = None
        for attempt in range(1, self.settings.retry_attempts + 1):
            try:
                return operation()
            except ValueError:
                raise
            except Exception as error:
                last_error = error
                if attempt >= self.settings.retry_attempts:
                    break
                LOGGER.warning(
                    "%s failed on attempt %s/%s; retrying in %.2fs: %s",
                    operation_name,
                    attempt,
                    self.settings.retry_attempts,
                    self.settings.retry_backoff_seconds,
                    error,
                )
                if self.settings.retry_backoff_seconds > 0:
                    time.sleep(self.settings.retry_backoff_seconds)
        assert last_error is not None
        raise last_error
