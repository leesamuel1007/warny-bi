"""Runtime object factory for the local FOSS backend."""

from __future__ import annotations

from warnybi.config import EnvSettings, RuntimeSettings
from warnybi.ollama import OllamaClient
from warnybi.sql import SqlClient
from warnybi.vector import OpenSearchIndex
from warnybi.workflows.query import AnswerPrompt, IntentPrompt, LocalRagPipeline


class RuntimeFactory:
    """Builds configured WARNY-BI runtime objects."""

    def __init__(self, settings: RuntimeSettings | None = None) -> None:
        self.settings = settings or EnvSettings().load()

    def sql(self) -> SqlClient:
        return SqlClient(self.settings.sql)

    def ollama(self) -> OllamaClient:
        return OllamaClient(self.settings.ollama, self.settings.answer)

    def vector(self) -> OpenSearchIndex:
        return OpenSearchIndex(self.settings.opensearch)

    def rag(self) -> LocalRagPipeline:
        return LocalRagPipeline(
            self.settings,
            self.ollama(),
            self.vector(),
            IntentPrompt(self.settings),
            AnswerPrompt(self.settings),
            self.sql(),
        )

    def ingestion(self):
        from warnybi.workflows.ingest import IngestionPipeline

        return IngestionPipeline(self.settings, self.sql(), self.ollama(), self.vector())
