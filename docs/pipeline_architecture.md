# WARNY-BI Pipeline Architecture

## Project Direction

WARNY-BI has one shared dataset and two implementation paths:

- Azure path: the course-submission target.
- FOSS path: the local development and fallback path.

Both paths use the same source data, SQL RAG view shape, and Power BI output
schema so results can be compared.

Raw CSV files are the local source of truth. Python generates SQL-ready
processed CSV files under `data/processed/` and a reviewable
`data/processed/schema.json`; SQL scripts then build relational tables and the
RAG-readable view from those processed files.

## Azure Path

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

Current Azure state:

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

## FOSS Path

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

Expected local components are MinIO or filesystem storage, Qdrant, local
embeddings, an Ollama/open-weight model, and a small API wrapper if Power BI
should not call services directly.

## Repository Layout

```text
term_project/
  data/
    raw/                 # Source CSV files
    processed/           # Generated SQL-ready CSVs and schema.json
    images/              # Warning-light image files
  docs/                  # Project documentation
  scripts/
    python/              # Runnable Python commands
    sql/                 # SQL scripts for views, tables, and checks
  src/
    warny_bi/            # Reusable Python package
    rag_service/         # Local/FOSS RAG API service
    powerbi/             # Power BI artifacts
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

`schema.json` is generated from CSV files for operator validation. It records
column names, inferred data types, preferred preprocessing types, suggested SQL
types, null-like counts, primary keys, foreign keys, and normalization rules.

## Versioned Iteration Surfaces

Keep these artifacts versioned:

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
