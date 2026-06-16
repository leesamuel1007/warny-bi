"""Run WARNY-BI SQL-to-OpenSearch ingestion."""

from warnybi.workflows.ingest import OpenSearchIngestCli


if __name__ == "__main__":
    raise SystemExit(OpenSearchIngestCli().run())
