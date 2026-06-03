# WARNY-BI Project Scope

WARNY-BI is a DS545 term project for warning-light triage and business
intelligence. The system should help a user describe a dashboard warning-light
case, retrieve relevant warning-light, recall, and service-routing evidence,
and return structured rows that can be shown in Power BI.

The system is not a certified diagnosis tool. Its job is to provide
evidence-grounded triage: what the warning light usually means, how urgent it
is, whether recall evidence may be relevant, and what service route should be
prioritized.

## Data Preparation

The source data consists of CSV files and warning-light images:

- warning-light catalog
- warning-light image catalog
- recall records
- maintenance and service routing map
- validation scenarios
- source/license metadata

The preprocessing script validates these files, profiles the CSVs, generates a
reviewable `schema.json`, and writes SQL-ready CSV files under
`data/processed/`.

```bash
python3 scripts/python/preprocess_dataset.py validate
python3 scripts/python/preprocess_dataset.py eda
python3 scripts/python/preprocess_dataset.py schema --csv-dir data/raw --output-file data/processed/schema.json
python3 scripts/python/preprocess_dataset.py clean --schema-file data/processed/schema.json
```

Raw CSV files remain the authoritative dataset. The generated schema helps with
SQL table design and preprocessing rules.

## SQL Database

Both the Azure and FOSS paths use SQL tables built from the processed CSV files.
The current local setup uses SQL Server in Docker and DBeaver for manual CSV
import.

Current SQL scripts:

- `scripts/sql/01_create_tables.sql`: creates the six processed-data tables.
- `scripts/sql/02_load_data.sql`: reserved for scripted loading.
- `scripts/sql/03_create_rag_view.sql`: creates `dbo.vw_rag_documents`.
- `scripts/sql/04_verify.sql`: checks row counts, joins, and the retrieval view.

The retrieval view currently contains 585 rows from warning lights, recalls,
maintenance routes, image metadata, and validation scenarios.

## FOSS RAG Path

The local FOSS pipeline is the development testbed:

```text
SQL Server view
-> Ollama embedding model
-> Qdrant vector index
-> Ollama chat model
-> FastAPI endpoint
-> Power BI / tester query flow
```

Current model choices:

- Embeddings: `mxbai-embed-large`
- Chat/RAG answers: `qwen2.5:14b`

The next implementation step is to ingest `dbo.vw_rag_documents` into Qdrant.
After that, the API can accept a user’s text description of warning lights,
retrieve supporting rows, and return a grounded answer plus evidence rows.

## Azure Path

The Azure path should mirror the same data model where possible:

```text
processed CSVs
-> Azure Storage / Azure SQL
-> SQL retrieval view
-> Azure AI Search
-> Microsoft Foundry OpenAI models
-> Power Query
-> Power BI dashboard
```

The Azure model deployments are `text-embedding-3-large` and `gpt-4o`.

## Power BI

Power BI should show structured evidence rows instead of relying on an LLM to
perform chart aggregation. Expected fields include vehicle information,
warning-light name, severity, recall relevance, recommended service, evidence
text, and retrieval score.

Image upload is a later extension. The first customer-facing mode should accept
text descriptions of dashboard warning lights.
