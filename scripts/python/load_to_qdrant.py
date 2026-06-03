#!/usr/bin/env python3
"""Run WARNY-BI SQL-to-Qdrant ingestion."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
load_dotenv(PROJECT_ROOT / "config" / ".env")

from rag_service.config import IngestionConfig, OllamaConfig, QdrantConfig, SqlConfig
from rag_service.db import SqlConnectionFactory, SqlDocumentReader
from rag_service.embeddings import OllamaEmbeddingClient
from rag_service.ingest import QdrantIngestionService
from rag_service.vector_store import QdrantVectorStore


class QdrantIngestionCli:
    """CLI entrypoint for SQL-to-Qdrant ingestion."""

    DEFAULT_SQL_DRIVER = "ODBC Driver 18 for SQL Server"
    DEFAULT_SQL_SERVER = "127.0.0.1,1433"
    DEFAULT_SQL_DATABASE = "warny_bi"
    DEFAULT_SQL_VIEW = "dbo.vw_rag_documents"
    DEFAULT_QDRANT_URL = "http://127.0.0.1:16333"
    DEFAULT_COLLECTION = "warny_bi_rag"
    DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
    DEFAULT_EMBED_MODEL = "mxbai-embed-large"
    DEFAULT_CHAT_MODEL = "qwen2.5:14b"
    DEFAULT_TEST_QUERY = "2020 Hyundai Elantra yellow engine light recall"

    def parse_args(self) -> argparse.Namespace:
        parser = argparse.ArgumentParser(description="Load dbo.vw_rag_documents into Qdrant")
        parser.add_argument("--sql-driver", default=os.getenv("WARNY_SQL_DRIVER", self.DEFAULT_SQL_DRIVER))
        parser.add_argument("--sql-server", default=os.getenv("WARNY_SQL_SERVER", self.DEFAULT_SQL_SERVER))
        parser.add_argument("--sql-database", default=os.getenv("WARNY_SQL_DATABASE", self.DEFAULT_SQL_DATABASE))
        parser.add_argument("--sql-user", default=os.getenv("WARNY_SQL_USER"))
        parser.add_argument("--sql-password", default=os.getenv("WARNY_SQL_PASSWORD"))
        parser.add_argument("--sql-connection-string", default=os.getenv("WARNY_SQL_CONNECTION_STRING"))
        parser.add_argument("--sql-view", default=os.getenv("WARNY_SQL_VIEW", self.DEFAULT_SQL_VIEW))
        parser.add_argument("--qdrant-url", default=os.getenv("WARNY_QDRANT_URL", self.DEFAULT_QDRANT_URL))
        parser.add_argument("--collection", default=os.getenv("WARNY_QDRANT_COLLECTION", self.DEFAULT_COLLECTION))
        parser.add_argument("--ollama-url", default=os.getenv("WARNY_OLLAMA_URL", self.DEFAULT_OLLAMA_URL))
        parser.add_argument("--embed-model", default=os.getenv("WARNY_EMBED_MODEL", self.DEFAULT_EMBED_MODEL))
        parser.add_argument("--chat-model", default=os.getenv("WARNY_CHAT_MODEL", self.DEFAULT_CHAT_MODEL))
        parser.add_argument("--batch-size", type=int, default=int(os.getenv("WARNY_EMBED_BATCH_SIZE", "16")))
        parser.add_argument("--timeout-seconds", type=float, default=float(os.getenv("WARNY_OLLAMA_TIMEOUT", "120")))
        parser.add_argument("--recreate", action="store_true", help="Delete and recreate the Qdrant collection")
        parser.add_argument("--test-query", default=os.getenv("WARNY_TEST_QUERY", self.DEFAULT_TEST_QUERY))
        parser.add_argument("--test-limit", type=int, default=int(os.getenv("WARNY_TEST_LIMIT", "5")))
        return parser.parse_args()

    def run(self) -> int:
        args = self.parse_args()
        service = self.create_service(args)
        result = service.run()
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0

    def create_service(self, args: argparse.Namespace) -> QdrantIngestionService:
        sql_config = SqlConfig(
            driver=args.sql_driver,
            server=args.sql_server,
            database=args.sql_database,
            user=args.sql_user,
            password=args.sql_password,
            connection_string_override=args.sql_connection_string,
        )
        ollama_config = OllamaConfig(
            base_url=args.ollama_url,
            embedding_model=args.embed_model,
            chat_model=args.chat_model,
            timeout_seconds=args.timeout_seconds,
        )
        qdrant_config = QdrantConfig(
            url=args.qdrant_url,
            collection_name=args.collection,
            recreate=args.recreate,
        )
        ingestion_config = IngestionConfig(
            sql_view=args.sql_view,
            batch_size=args.batch_size,
            test_query=args.test_query,
            test_limit=args.test_limit,
        )
        connection_factory = SqlConnectionFactory(sql_config)
        document_reader = SqlDocumentReader(connection_factory, ingestion_config.sql_view)
        embedding_client = OllamaEmbeddingClient(ollama_config)
        vector_store = QdrantVectorStore(qdrant_config)
        return QdrantIngestionService(
            config=ingestion_config,
            ollama_config=ollama_config,
            qdrant_config=qdrant_config,
            document_reader=document_reader,
            embedding_client=embedding_client,
            vector_store=vector_store,
        )


if __name__ == "__main__":
    raise SystemExit(QdrantIngestionCli().run())
