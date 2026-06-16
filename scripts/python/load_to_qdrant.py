#!/usr/bin/env python3
"""Run WARNY-BI SQL-to-Qdrant ingestion."""

from warnybi.pipeline import QdrantIngestCli


if __name__ == "__main__":
    raise SystemExit(QdrantIngestCli().run())
