# WARNY-BI Pipeline Architecture

## Overview

WARNY-BI uses one dataset in two ways:

- **Azure path**: the main course-submission pipeline.
- **FOSS path**: the local development and fallback pipeline.

Both paths start with the same CSV/image data and use the same SQL retrieval
view shape. This keeps the local pipeline useful for testing before Azure
deployment.

The project flow is:

```text
raw CSV/images
-> Python validation and preprocessing
-> processed CSVs
-> SQL tables
-> SQL retrieval view
-> vector search / AI Search
-> LLM answer generation
-> Power BI evidence display
```

Raw CSV files are the authoritative dataset. Python writes SQL-ready processed
files under `data/processed/`; SQL scripts then create relational tables and
the single RAG retrieval view.

## Azure Pipeline

```text
Local raw CSV/images
-> Python validation, EDA, and SQL-ready CSV preprocessing
-> processed CSVs and schema.json
-> Azure Storage
-> Azure SQL staging and relational tables
-> RAG-readable SQL view
-> Azure AI Search index
-> Microsoft Foundry OpenAI Entrypoint
-> Power Query M
-> Power BI dashboard
```

Current Azure resources:

- Resource group: `warny-bi-rag`
- Primary region: Japan East
- Active model host: Microsoft Foundry project/resource with OpenAI Entrypoint
- Active model deployments: `gpt-4o`, `text-embedding-3-large`
- Active data services: Azure Storage, Azure SQL Server/Database, Azure AI
  Search
- Removed resources: old East US 2 Foundry setup and old standalone Azure
  OpenAI service

Do not commit API keys, SQL passwords, endpoint keys, connection strings, or
Power Query files with live secrets.

## Local FOSS Pipeline

```text
Local raw CSV/images
-> Python validation, EDA, and SQL-ready CSV preprocessing
-> processed CSVs and schema.json
-> local object/file storage
-> local SQL database and RAG-readable SQL view
-> local vector index
-> local LLM endpoint
-> Power Query M
-> Power BI dashboard
```

Current local setup:

- SQL Server in Docker, kept local-only on `127.0.0.1:1433`.
- DBeaver for SQL Server connection, table inspection, and manual CSV import.
- `scripts/sql/01_create_tables.sql` to create the six processed-data tables.
- `scripts/sql/03_create_rag_view.sql` to create `dbo.vw_rag_documents`.
- `scripts/sql/04_verify.sql` to verify table loads and the RAG view.
- Qdrant in Docker, kept local-only on custom host ports for vector storage.
- Ollama on the Ubuntu host with `mxbai-embed-large` for embeddings and
  `qwen2.5:14b` for local chat/RAG answer generation.
- A root uv project with `pyproject.toml`, `uv.lock`, and exported
  `requirements.txt` for Python loader, ingestion, and FastAPI code.

CSV loading is currently done through DBeaver import into SQL Server. When this
needs to be automated, the loading step should move into
`scripts/sql/02_load_data.sql` or a Python loader.

## Repository Layout

```text
data/
  raw/                   # Source CSV files
  processed/             # Generated SQL-ready CSVs and schema.json
  images/                # Warning-light image files
docs/                    # Project documentation
scripts/
  python/                # Runnable Python commands
  sql/                   # SQL scripts for views, tables, and checks
src/
  warny_bi/              # Reusable Python package
  rag_service/           # Local/FOSS RAG API service
  powerbi/               # Power BI artifacts
```

The `warny_bi` package stores reusable class containers for CSV I/O, EDA,
validation, and schema-driven preprocessing. Runnable commands live under
`scripts/python/`.

The preprocessing entrypoint is:

```bash
python3 scripts/python/preprocess_dataset.py validate
python3 scripts/python/preprocess_dataset.py eda
python3 scripts/python/preprocess_dataset.py schema --csv-dir data/raw --output-file data/processed/schema.json
python3 scripts/python/preprocess_dataset.py clean --schema-file data/processed/schema.json
```

`schema.json` is generated from the CSV files. It records column names, inferred
types, suggested SQL types, key fields, and normalization rules.

## Files To Keep Versioned

Keep project logic in Git:

- SQL DDL, staging-load, merge, and view definitions
- Azure AI Search index and field mapping notes
- RAG system/user prompts
- Power Query M scripts
- EDA output, `schema.json`, and SQL schema review notes
- Dashboard design notes and report evidence

## Git And Data Policy

- Track small CSV files only if their license permits redistribution.
- Use Git LFS for images and `.pbix` files if they are committed.
- Keep generated processed data out of Git unless needed for report evidence.
- Keep `.env` files and credentials local.
- Use placeholders in committed scripts for endpoints, keys, server names, and
  database names.
