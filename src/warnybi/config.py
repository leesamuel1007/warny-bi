"""Runtime configuration loaded from the local environment."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class SqlSettings:
    driver: str
    server: str
    database: str
    user: str | None
    password: str | None
    connection_string: str | None

    def odbc_connection_string(self) -> str:
        if self.connection_string:
            return self.connection_string
        if not self.user or not self.password:
            raise ValueError("SQL_USER and SQL_PASSWORD are required unless SQL_CONNECTION_STRING is set")
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
class OpenSearchSettings:
    url: str
    index: str
    username: str | None
    password: str | None


@dataclass(frozen=True)
class OllamaSettings:
    url: str
    embed_model: str
    chat_model: str
    timeout_seconds: float

    @property
    def base_url(self) -> str:
        return self.url.rstrip("/")


@dataclass(frozen=True)
class ApiSettings:
    host: str
    port: int


@dataclass(frozen=True)
class AnswerSettings:
    temperature: float


@dataclass(frozen=True)
class RuntimeSettings:
    root: Path
    processed_dir: Path
    sql_view: str
    sql_load_batch_size: int
    embed_batch_size: int
    retry_attempts: int
    retry_backoff_seconds: float
    log_pipeline: str
    sql: SqlSettings
    opensearch: OpenSearchSettings
    ollama: OllamaSettings
    api: ApiSettings
    answer: AnswerSettings


class EnvSettings:
    """Loads `.env` once and returns typed runtime settings."""

    def __init__(self, root: Path | None = None) -> None:
        self.root = root or Path(__file__).resolve().parents[2]
        load_dotenv(self.root / "config" / ".env")

    def load(self) -> RuntimeSettings:
        return RuntimeSettings(
            root=self.root,
            processed_dir=self.path("DATA_DIR"),
            sql_view=self.required("RAG_VIEW"),
            sql_load_batch_size=self.integer("SQL_LOAD_BATCH_SIZE"),
            embed_batch_size=self.integer("EMBED_BATCH_SIZE"),
            retry_attempts=self.integer("RETRY_ATTEMPTS"),
            retry_backoff_seconds=self.floating("RETRY_DELAY_SEC"),
            log_pipeline="foss_fastapi",
            sql=SqlSettings(
                driver=self.required("SQL_DRIVER"),
                server=self.required("SQL_SERVER"),
                database=self.required("SQL_DATABASE"),
                user=self.optional("SQL_USER"),
                password=self.optional("SQL_PASSWORD"),
                connection_string=self.optional("SQL_CONNECTION_STRING"),
            ),
            opensearch=OpenSearchSettings(
                url=self.required("OPENSEARCH_URL"),
                index=self.required("OPENSEARCH_INDEX"),
                username=self.optional("OPENSEARCH_USERNAME"),
                password=self.optional("OPENSEARCH_PASSWORD"),
            ),
            ollama=OllamaSettings(
                url=self.required("OLLAMA_URL"),
                embed_model=self.required("EMBEDDING_MODEL"),
                chat_model=self.required("CHAT_MODEL"),
                timeout_seconds=self.floating("OLLAMA_TIMEOUT"),
            ),
            api=ApiSettings(
                host=self.required("API_HOST"),
                port=self.integer("API_PORT"),
            ),
            answer=AnswerSettings(
                temperature=self.floating("CHAT_TEMPERATURE"),
            ),
        )

    def required(self, name: str) -> str:
        value = os.getenv(name)
        if value is None or not value.strip():
            raise ValueError(f"{name} is required in config/.env")
        return value.strip()

    def optional(self, name: str) -> str | None:
        value = os.getenv(name)
        if value is None or not value.strip():
            return None
        return value.strip()

    def integer(self, name: str) -> int:
        return int(self.required(name))

    def floating(self, name: str) -> float:
        return float(self.required(name))

    def path(self, name: str) -> Path:
        value = Path(self.required(name))
        if value.is_absolute():
            return value
        return self.root / value
