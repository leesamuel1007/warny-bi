"""FastAPI service workflow."""

from __future__ import annotations

import argparse
import logging

from warnybi.config import EnvSettings
from warnybi.workflows.factory import RuntimeFactory


class ApiCli:
    """CLI for local FastAPI service."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Run WARNY-BI local RAG API")
        parser.parse_args()

        settings = EnvSettings().load()
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )

        import uvicorn
        from warnybi.api import ApiServer

        server = ApiServer(RuntimeFactory(settings).rag(), settings)
        uvicorn.run(server.app, host=settings.api.host, port=settings.api.port)
        return 0
