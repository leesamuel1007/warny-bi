"""Query logging classes for WARNY-BI RAG services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from rag_service.config import QueryLogConfig, SqlConfig
from rag_service.db import SqlConnectionFactory
from rag_service.documents import RagAnswer, SearchResult


class QueryLogger:
    """Base query logger interface."""

    def log(self, result: RagAnswer) -> None:
        raise NotImplementedError


class NullQueryLogger(QueryLogger):
    """No-op logger used when local logging is disabled."""

    def log(self, result: RagAnswer) -> None:
        return None


@dataclass(frozen=True)
class QueryLogPayload:
    """Serializable SQL log payload."""

    query_id: str
    created_at_utc: datetime
    pipeline: str
    user_prompt: str
    top_k: int
    include_image_evidence: bool
    answer_json: str
    citations_json: str
    upstream_response_json: str


class QueryLogPayloadBuilder:
    """Builds the shared dbo.query_log JSON payload from a local RAG answer."""

    def build(self, result: RagAnswer, pipeline: str) -> QueryLogPayload:
        answer = result.answer.to_dict()
        evidence = [self.evidence_payload(evidence_item) for evidence_item in result.evidence]
        response = {
            "query": result.query,
            "top_k": result.top_k,
            "include_image_evidence": result.include_image_evidence,
            "answer": answer,
            "evidence": evidence,
            "parsed_intent": result.parsed_intent.to_dict(),
        }
        return QueryLogPayload(
            query_id=str(uuid4()),
            created_at_utc=datetime.now(timezone.utc).replace(tzinfo=None),
            pipeline=pipeline,
            user_prompt=result.query,
            top_k=result.top_k,
            include_image_evidence=result.include_image_evidence,
            answer_json=self.dumps(answer),
            citations_json=self.dumps(evidence),
            upstream_response_json=self.dumps(response),
        )

    def evidence_payload(self, evidence: SearchResult) -> dict[str, Any]:
        payload = evidence.to_dict()
        payload["content"] = evidence.content
        return payload

    def dumps(self, value: object) -> str:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class SqlQueryLogger(QueryLogger):
    """Writes local/FOSS RAG interactions to dbo.query_log."""

    def __init__(
        self,
        config: QueryLogConfig,
        connection_factory: SqlConnectionFactory,
        payload_builder: QueryLogPayloadBuilder | None = None,
    ) -> None:
        self.config = config
        self.connection_factory = connection_factory
        self.payload_builder = payload_builder or QueryLogPayloadBuilder()

    @classmethod
    def from_sql_config(cls, config: QueryLogConfig, sql_config: SqlConfig) -> "SqlQueryLogger":
        return cls(config=config, connection_factory=SqlConnectionFactory(sql_config))

    def log(self, result: RagAnswer) -> None:
        if not self.config.enabled:
            return None
        payload = self.payload_builder.build(result, self.config.pipeline)
        with self.connection_factory.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO dbo.query_log (
                    query_id,
                    created_at_utc,
                    pipeline,
                    user_prompt,
                    top_k,
                    include_image_evidence,
                    answer_json,
                    citations_json,
                    azure_response_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                payload.query_id,
                payload.created_at_utc,
                payload.pipeline,
                payload.user_prompt,
                payload.top_k,
                payload.include_image_evidence,
                payload.answer_json,
                payload.citations_json,
                payload.upstream_response_json,
            )
            connection.commit()
        return None
