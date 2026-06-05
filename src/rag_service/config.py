"""Configuration classes for WARNY-BI RAG services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SqlConfig:
    """SQL Server connection settings."""

    driver: str
    server: str
    database: str
    user: str | None = None
    password: str | None = None
    connection_string_override: str | None = None

    def connection_string(self) -> str:
        if self.connection_string_override:
            return self.connection_string_override
        if not self.user or not self.password:
            raise ValueError("SQL user and password are required unless a full connection string is provided")
        return (
            f"DRIVER={{{self.driver}}};"
            f"SERVER={self.server};"
            f"DATABASE={self.database};"
            f"UID={self.user};"
            f"PWD={self.password};"
            "Encrypt=yes;"
            "TrustServerCertificate=yes;"
        )


@dataclass(frozen=True)
class OllamaConfig:
    """Ollama endpoint and model settings."""

    base_url: str
    embedding_model: str
    chat_model: str
    timeout_seconds: float

    def normalized_base_url(self) -> str:
        return self.base_url.rstrip("/")


@dataclass(frozen=True)
class QdrantConfig:
    """Qdrant endpoint and collection settings."""

    url: str
    collection_name: str
    recreate: bool = False


@dataclass(frozen=True)
class IngestionConfig:
    """Runtime settings for SQL-to-Qdrant ingestion."""

    sql_view: str
    batch_size: int
    test_query: str | None = None
    test_limit: int = 5

    def validate(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be at least 1")
        if self.test_limit < 1:
            raise ValueError("test_limit must be at least 1")


@dataclass(frozen=True)
class AnswerConfig:
    """Runtime settings for RAG answer generation."""

    default_top_k: int = 5
    max_evidence_chars: int = 800
    temperature: float = 0.0
    candidate_multiplier: int = 4
    max_candidates: int = 30

    def validate_top_k(self, top_k: int) -> int:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        return top_k

    def candidate_limit(self, top_k: int) -> int:
        if self.candidate_multiplier < 1:
            raise ValueError("candidate_multiplier must be at least 1")
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be at least 1")
        return min(max(top_k, top_k * self.candidate_multiplier), self.max_candidates)


@dataclass(frozen=True)
class PromptTemplateConfig:
    """Editable prompt template locations."""

    answer_template_path: Path
    evidence_template_path: Path
    intent_template_path: Path

    def validate(self) -> None:
        if not self.answer_template_path.is_file():
            raise FileNotFoundError(f"Answer prompt template not found: {self.answer_template_path}")
        if not self.evidence_template_path.is_file():
            raise FileNotFoundError(f"Evidence prompt template not found: {self.evidence_template_path}")
        if not self.intent_template_path.is_file():
            raise FileNotFoundError(f"Intent prompt template not found: {self.intent_template_path}")


@dataclass(frozen=True)
class ApiConfig:
    """FastAPI server settings."""

    host: str
    port: int
