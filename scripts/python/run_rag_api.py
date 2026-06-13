#!/usr/bin/env python3
"""Run the WARNY-BI FastAPI RAG service."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import uvicorn


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
load_dotenv(PROJECT_ROOT / "config" / ".env")

from rag_service.ag import (
    OllamaChatClient,
    OllamaQueryIntentExtractor,
    PromptTemplateReader,
    RagAnswerService,
    RagPromptBuilder,
)
from rag_service.app import WarnyBiApi
from rag_service.config import AnswerConfig, OllamaConfig, PromptTemplateConfig, QdrantConfig
from rag_service.config import QueryLogConfig, SqlConfig
from rag_service.embeddings import OllamaEmbeddingClient
from rag_service.query_log import NullQueryLogger, QueryLogger, SqlQueryLogger
from rag_service.retrieval import QueryTermExtractor, SearchResultReranker
from rag_service.vector_store import QdrantVectorStore


class RagApiCli:
    """CLI entrypoint for the local FastAPI RAG service."""

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 18080
    DEFAULT_QDRANT_URL = "http://127.0.0.1:16333"
    DEFAULT_COLLECTION = "warny_bi_rag"
    DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
    DEFAULT_EMBED_MODEL = "mxbai-embed-large"
    DEFAULT_CHAT_MODEL = "qwen2.5:14b"
    DEFAULT_ANSWER_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "rag_answer_foss.txt"
    DEFAULT_EVIDENCE_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "evidence_block_foss.txt"
    DEFAULT_INTENT_PROMPT_PATH = PROJECT_ROOT / "config" / "prompts" / "query_intent_foss.txt"

    def parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Run WARNY-BI local RAG API")
        parser.add_argument("--host", default=os.getenv("WARNY_API_HOST", self.DEFAULT_HOST))
        parser.add_argument("--port", type=int, default=int(os.getenv("WARNY_API_PORT", str(self.DEFAULT_PORT))))
        parser.add_argument("--qdrant-url", default=os.getenv("WARNY_QDRANT_URL", self.DEFAULT_QDRANT_URL))
        parser.add_argument("--collection", default=os.getenv("WARNY_QDRANT_COLLECTION", self.DEFAULT_COLLECTION))
        parser.add_argument("--ollama-url", default=os.getenv("WARNY_OLLAMA_URL", self.DEFAULT_OLLAMA_URL))
        parser.add_argument("--embed-model", default=os.getenv("WARNY_EMBED_MODEL", self.DEFAULT_EMBED_MODEL))
        parser.add_argument("--chat-model", default=os.getenv("WARNY_CHAT_MODEL", self.DEFAULT_CHAT_MODEL))
        parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("WARNY_OLLAMA_TIMEOUT", "120")))
        parser.add_argument("--default-top-k", type=int, default=int(os.getenv("WARNY_DEFAULT_TOP_K", "5")))
        parser.add_argument("--max-evidence-chars", type=int, default=int(os.getenv("WARNY_MAX_EVIDENCE_CHARS", "800")))
        parser.add_argument("--temperature", type=float, default=float(os.getenv("WARNY_CHAT_TEMPERATURE", "0")))
        parser.add_argument(
            "--candidate-multiplier",
            type=int,
            default=int(os.getenv("WARNY_CANDIDATE_MULTIPLIER", "4")),
        )
        parser.add_argument("--max-candidates", type=int, default=int(os.getenv("WARNY_MAX_CANDIDATES", "30")))
        parser.add_argument("--log-enabled", action="store_true", default=self.bool_from_env("WARNY_LOG_ENABLED", False))
        parser.add_argument("--log-pipeline", default=os.getenv("WARNY_LOG_PIPELINE", "foss_fastapi"))
        parser.add_argument(
            "--answer-prompt-path",
            type=Path,
            default=self.path_from_env("WARNY_FOSS_ANSWER_PROMPT_PATH", self.DEFAULT_ANSWER_PROMPT_PATH),
        )
        parser.add_argument(
            "--evidence-prompt-path",
            type=Path,
            default=self.path_from_env("WARNY_FOSS_EVIDENCE_PROMPT_PATH", self.DEFAULT_EVIDENCE_PROMPT_PATH),
        )
        parser.add_argument(
            "--intent-prompt-path",
            type=Path,
            default=self.path_from_env("WARNY_FOSS_INTENT_PROMPT_PATH", self.DEFAULT_INTENT_PROMPT_PATH),
        )
        return parser.parse_args()

    def bool_from_env(self, name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def path_from_env(self, name: str, default_path: Path) -> Path:
        value = os.getenv(name)
        if not value:
            return default_path
        path = Path(value)
        if path.is_absolute():
            return path
        return PROJECT_ROOT / path

    def run(self) -> int:
        args = self.parse_args()
        api = self.create_api(args)
        uvicorn.run(api.app, host=args.host, port=args.port)
        return 0

    def create_api(self, args: argparse.Namespace) -> WarnyBiApi:
        ollama_config = OllamaConfig(
            base_url=args.ollama_url,
            embedding_model=args.embed_model,
            chat_model=args.chat_model,
            timeout_seconds=args.timeout_seconds,
        )
        qdrant_config = QdrantConfig(
            url=args.qdrant_url,
            collection_name=args.collection,
            recreate=False,
        )
        answer_config = AnswerConfig(
            default_top_k=args.default_top_k,
            max_evidence_chars=args.max_evidence_chars,
            temperature=args.temperature,
            candidate_multiplier=args.candidate_multiplier,
            max_candidates=args.max_candidates,
        )
        template_config = PromptTemplateConfig(
            answer_template_path=args.answer_prompt_path,
            evidence_template_path=args.evidence_prompt_path,
            intent_template_path=args.intent_prompt_path,
        )
        embedding_client = OllamaEmbeddingClient(ollama_config)
        vector_store = QdrantVectorStore(qdrant_config)
        reranker = SearchResultReranker(QueryTermExtractor())
        template_reader = PromptTemplateReader(template_config)
        prompt_builder = RagPromptBuilder(answer_config, template_reader)
        chat_client = OllamaChatClient(ollama_config, answer_config)
        intent_extractor = OllamaQueryIntentExtractor(chat_client, template_reader)
        answer_service = RagAnswerService(
            answer_config=answer_config,
            embedding_client=embedding_client,
            vector_store=vector_store,
            reranker=reranker,
            intent_extractor=intent_extractor,
            prompt_builder=prompt_builder,
            chat_client=chat_client,
        )
        return WarnyBiApi(answer_service, self.create_query_logger(args))

    def create_query_logger(self, args: argparse.Namespace) -> QueryLogger:
        log_config = QueryLogConfig(
            enabled=args.log_enabled,
            pipeline=args.log_pipeline,
        )
        if not log_config.enabled:
            return NullQueryLogger()
        sql_config = SqlConfig(
            driver=os.getenv("WARNY_SQL_DRIVER", "ODBC Driver 18 for SQL Server"),
            server=os.getenv("WARNY_SQL_SERVER", "127.0.0.1,1433"),
            database=os.getenv("WARNY_SQL_DATABASE", "warny_bi"),
            user=os.getenv("WARNY_SQL_USER"),
            password=os.getenv("WARNY_SQL_PASSWORD"),
            connection_string_override=os.getenv("WARNY_SQL_CONNECTION_STRING"),
        )
        return SqlQueryLogger.from_sql_config(log_config, sql_config)


if __name__ == "__main__":
    raise SystemExit(RagApiCli().run())
