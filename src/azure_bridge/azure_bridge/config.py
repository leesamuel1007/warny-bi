"""Environment configuration for the Azure bridge."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from azure_bridge.prompts import RoleInformationReader


@dataclass(frozen=True)
class AzureOpenAIConfig:
    """Azure OpenAI and Azure AI Search settings."""

    endpoint: str
    api_key: str
    chat_deployment: str
    search_endpoint: str
    search_key: str
    search_index: str
    api_version: str
    top_k: int
    strictness: int
    query_type: str
    semantic_configuration: str | None
    embedding_deployment: str | None
    search_filter: str | None
    role_information: str
    timeout_seconds: float

    def normalized_endpoint(self) -> str:
        return self.endpoint.rstrip("/")

    def normalized_search_endpoint(self) -> str:
        return self.search_endpoint.rstrip("/")


@dataclass(frozen=True)
class SqlLogConfig:
    """Azure SQL logging settings."""

    enabled: bool
    pipeline: str


@dataclass(frozen=True)
class AzureBridgeConfig:
    """Complete Azure bridge settings."""

    azure_openai: AzureOpenAIConfig
    sql_log: SqlLogConfig

    @classmethod
    def from_env(cls) -> "AzureBridgeConfig":
        return cls(
            azure_openai=AzureOpenAIConfig(
                endpoint=required_env("WARNY_AZURE_OPENAI_ENDPOINT"),
                api_key=required_env("WARNY_AZURE_OPENAI_KEY"),
                chat_deployment=required_env("WARNY_AZURE_CHAT_DEPLOYMENT"),
                search_endpoint=required_env("WARNY_AZURE_SEARCH_ENDPOINT"),
                search_key=required_env("WARNY_AZURE_SEARCH_KEY"),
                search_index=required_env("WARNY_AZURE_SEARCH_INDEX"),
                api_version=optional_env("WARNY_AZURE_OPENAI_API_VERSION") or "2024-05-01-preview",
                top_k=optional_int("WARNY_AZURE_TOP_K", 5),
                strictness=optional_int("WARNY_AZURE_STRICTNESS", 3),
                query_type=optional_env("WARNY_AZURE_QUERY_TYPE") or "simple",
                semantic_configuration=optional_env("WARNY_AZURE_SEMANTIC_CONFIGURATION"),
                embedding_deployment=optional_env("WARNY_AZURE_EMBEDDING_DEPLOYMENT"),
                search_filter=optional_env("WARNY_AZURE_FILTER"),
                role_information=RoleInformationReader(
                    explicit_text=optional_env("WARNY_ROLE_INFORMATION"),
                    prompt_path=prompt_path_from_env(),
                ).read(),
                timeout_seconds=optional_float("WARNY_AZURE_TIMEOUT_SECONDS", 60.0),
            ),
            sql_log=SqlLogConfig(
                enabled=optional_bool("WARNY_QUERY_LOG_ENABLED", True),
                pipeline=optional_env("WARNY_QUERY_LOG_PIPELINE") or "azure",
            ),
        )


def required_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"Missing required app setting: {name}")
    return value.strip()


def optional_env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return value.strip()


def optional_int(name: str, default: int) -> int:
    value = optional_env(name)
    if value is None:
        return default
    return int(value)


def optional_float(name: str, default: float) -> float:
    value = optional_env(name)
    if value is None:
        return default
    return float(value)


def optional_bool(name: str, default: bool) -> bool:
    value = optional_env(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def prompt_path_from_env() -> Path | None:
    explicit_path = optional_env("WARNY_ROLE_INFORMATION_PATH")
    if explicit_path:
        return Path(explicit_path)
    repo_prompt_path = Path(__file__).resolve().parents[3] / "config" / "prompts" / "rag_answer.txt"
    return repo_prompt_path
