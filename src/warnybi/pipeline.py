"""WARNY-BI local pipeline orchestration and CLI entrypoints."""

from __future__ import annotations

import argparse
import json
import logging
from typing import Any

import uvicorn

from warnybi.api import ApiServer
from warnybi.config import EnvSettings, RuntimeSettings
from warnybi.models import DashboardAnswer, IngestionResult, RagDocument, RagResponse, SearchResult
from warnybi.ollama import OllamaClient
from warnybi.sql import SqlClient
from warnybi.vector import QdrantIndex


DEFAULT_TOP_K = 5
MAX_SEARCH_LIMIT = 100


class Prompt:
    """Renders the single FOSS answer prompt with query and retrieved evidence."""

    def __init__(self, settings: RuntimeSettings) -> None:
        self.settings = settings
        prompt_path = settings.root / "config" / "prompts" / "rag_answer_foss.txt"
        if not prompt_path.is_file():
            raise FileNotFoundError(f"FOSS answer prompt not found: {prompt_path}")
        self.template = prompt_path.read_text(encoding="utf-8").strip()

    def render(self, query: str, evidence: tuple[SearchResult, ...]) -> str:
        evidence_text = "\n\n".join(
            f"Evidence [{index + 1}]\n{item.evidence_text()}"
            for index, item in enumerate(evidence)
        )
        return self.template.replace("{query}", query).replace("{evidence}", evidence_text)


class LocalRagPipeline:
    """Runs the local FOSS RAG query flow: prompt, vector search, one LLM answer."""

    def __init__(
        self,
        settings: RuntimeSettings,
        ollama: OllamaClient,
        vector: QdrantIndex,
        prompt: Prompt,
        sql: SqlClient,
    ) -> None:
        self.settings = settings
        self.ollama = ollama
        self.vector = vector
        self.prompt = prompt
        self.sql = sql

    def answer(self, query: str, top_k: int | None = None, include_image_evidence: bool = False) -> RagResponse:
        clean_query = query.strip()
        if not clean_query:
            raise ValueError("query must not be blank")
        limit = top_k or DEFAULT_TOP_K
        if limit < 1:
            raise ValueError("top_k must be at least 1")

        query_vector = self.ollama.embed_query(clean_query)
        evidence = self.retrieve_evidence(query_vector, limit, include_image_evidence)
        answer_text = self.ollama.complete(self.prompt.render(clean_query, evidence))
        answer = DashboardAnswer.from_payload(self.json_object(answer_text))
        response = RagResponse(
            query=clean_query,
            top_k=limit,
            include_image_evidence=include_image_evidence,
            answer=answer,
            evidence=evidence,
        )
        self.log_response(response)
        return response

    def retrieve_evidence(self, query_vector: list[float], limit: int, include_image_evidence: bool) -> tuple[SearchResult, ...]:
        if include_image_evidence:
            return self.vector.search(query_vector, limit, include_images=True)

        search_limit = limit
        results: tuple[SearchResult, ...] = ()
        while search_limit <= MAX_SEARCH_LIMIT:
            results = self.vector.search(query_vector, search_limit, include_images=False)
            if len(results) >= limit or len(results) < search_limit:
                break
            search_limit = min(search_limit * 2, MAX_SEARCH_LIMIT + 1)
        return tuple(item for item in results if not item.is_image())[:limit]

    def json_object(self, response_text: str) -> dict[str, Any]:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start < 0 or end < start:
            raise ValueError(f"LLM answer did not return a JSON object: {response_text}")
        payload = json.loads(response_text[start : end + 1])
        if not isinstance(payload, dict):
            raise ValueError("LLM answer JSON must be an object")
        return payload

    def log_response(self, response: RagResponse) -> None:
        self.sql.insert_query_log(response, self.settings.log_pipeline)


class IngestionPipeline:
    """Loads SQL retrieval documents into Qdrant."""

    def __init__(self, settings: RuntimeSettings, sql: SqlClient, ollama: OllamaClient, vector: QdrantIndex) -> None:
        self.settings = settings
        self.sql = sql
        self.ollama = ollama
        self.vector = vector

    def run(self, recreate: bool) -> IngestionResult:
        documents = [document for document in self.sql.read_documents(self.settings.sql_view) if document.content.strip()]
        if not documents:
            raise ValueError(f"No documents with content were read from {self.settings.sql_view}")

        first_vector = self.ollama.embed_texts([documents[0].content])[0]
        if recreate:
            self.vector.recreate_collection(len(first_vector))
        else:
            self.vector.ensure_collection(len(first_vector))
        self.vector.upsert([documents[0]], [first_vector])

        indexed = 1
        for batch in self.batches(documents[1:]):
            vectors = self.ollama.embed_texts([document.content for document in batch])
            self.vector.upsert(batch, vectors)
            indexed += len(batch)

        return IngestionResult(
            collection=self.settings.qdrant.collection,
            documents_read=len(documents),
            documents_indexed=indexed,
            embedding_model=self.settings.ollama.embed_model,
            qdrant_url=self.settings.qdrant.url,
        )

    def batches(self, documents: list[RagDocument]) -> list[list[RagDocument]]:
        size = self.settings.embed_batch_size
        if size < 1:
            raise ValueError("EMBED_BATCH_SIZE must be at least 1")
        return [documents[index : index + size] for index in range(0, len(documents), size)]


class RuntimeFactory:
    """Builds configured WARNY-BI runtime objects."""

    def __init__(self, settings: RuntimeSettings | None = None) -> None:
        self.settings = settings or EnvSettings().load()

    def sql(self) -> SqlClient:
        return SqlClient(self.settings.sql)

    def ollama(self) -> OllamaClient:
        return OllamaClient(self.settings.ollama, self.settings.answer)

    def vector(self) -> QdrantIndex:
        return QdrantIndex(self.settings.qdrant)

    def rag(self) -> LocalRagPipeline:
        return LocalRagPipeline(self.settings, self.ollama(), self.vector(), Prompt(self.settings), self.sql())

    def ingestion(self) -> IngestionPipeline:
        return IngestionPipeline(self.settings, self.sql(), self.ollama(), self.vector())


class DatabaseLoadCli:
    """CLI entrypoint for processed CSV to SQL loading."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Load processed WARNY-BI CSV files into SQL Server")
        parser.add_argument("--append", action="store_true", help="Append rows instead of clearing destination tables")
        args = parser.parse_args()
        settings = EnvSettings().load()
        results = SqlClient(settings.sql).load_processed_csvs(settings.processed_dir, settings.sql_load_batch_size, args.append)
        for result in results:
            print(f"{result.table_name}: loaded {result.rows_loaded} rows from {result.csv_path}")
        return 0


class QdrantIngestCli:
    """CLI entrypoint for SQL retrieval view to Qdrant ingestion."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Load dbo.vw_rag_documents into Qdrant")
        parser.add_argument("--recreate", action="store_true", help="Delete and recreate the Qdrant collection")
        args = parser.parse_args()
        result = RuntimeFactory().ingestion().run(recreate=args.recreate)
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return 0


class ApiCli:
    """CLI entrypoint for the local FastAPI service."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Run WARNY-BI local RAG API")
        parser.parse_args()
        settings = EnvSettings().load()
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        server = ApiServer(RuntimeFactory(settings).rag(), settings)
        uvicorn.run(server.app, host=settings.api.host, port=settings.api.port)
        return 0
