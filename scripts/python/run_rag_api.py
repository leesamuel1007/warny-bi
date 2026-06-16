#!/usr/bin/env python3
"""Run the WARNY-BI FastAPI RAG service."""

from warnybi.workflows.api import ApiCli


if __name__ == "__main__":
    raise SystemExit(ApiCli().run())
