# WARNY-BI Term Project

WARNY-BI is a Retrieval-Augmented Generation (RAG) and Business Intelligence
project for interpreting vehicle dashboard warning lights, matching related
recall evidence, recommending service-triage actions, and visualizing the
results in Power BI.

The project is designed for used-car drivers and service-related business
users, including used-car platforms, fleet operators, repair networks, and
insurance or roadside-assistance teams. The goal is not to provide certified
mechanical diagnosis. WARNY-BI provides evidence-grounded triage support:
warning-light severity, possible causes, recall relevance, recommended service
type, and source-backed evidence rows.

## Project Question

How can a RAG-powered BI system help drivers and service organizations
interpret warning-light cases, retrieve relevant recall and maintenance
information, and prioritize appropriate next actions?

## Data

The dataset contains the following information in separate .csv files: 

- a 64-class warning-light catalog
- warning-light image metadata and image files
- NHTSA recall records
- maintenance/service triage mappings
- validation scenarios
- source and license metadata

## Pipeline

The primary submission path uses Azure and Power BI:

```text
Raw CSV/images
-> Python validation, EDA, and SQL-ready CSV preprocessing
-> data/processed/*.csv and data/processed/schema.json
-> Azure Storage and Azure SQL
-> RAG-readable SQL view
-> Azure AI Search
-> Microsoft Foundry OpenAI model deployments
-> Power Query
-> Power BI dashboard
```

A parallel FOSS path is maintained for local development and fallback testing
using the same data contracts.

```text
Raw CSV/images 
-> Python validation, EDA, and SQL-ready CSV preprocessing
-> data/processed/*.csv and data/processed/schema.json
-> local object/file storage
-> local SQL database and RAG-readable SQL view
-> local vector index
-> local LLM endpoint
-> Power Query M
-> Power BI dashboard
```

## Local FOSS API

The local RAG API uses SQL Server, Qdrant, Ollama, and FastAPI. It reads runtime
settings from `config/.env`.

Start the API for Power BI:

```bash
scripts/bash/run_local_foss_api.sh
```

Refresh the Qdrant collection before starting the API:

```bash
scripts/bash/run_local_foss_api.sh --ingest
```

Recreate the Qdrant collection from `dbo.vw_rag_documents`:

```bash
scripts/bash/run_local_foss_api.sh --recreate
```

Test the API directly:

```bash
curl -X POST http://127.0.0.1:18080/query \
  -H "Content-Type: application/json" \
  -d '{
    "query":"yellow engine light recall",
    "make":"Hyundai",
    "model":"Elantra",
    "model_year":2020,
    "warning_light":"engine light",
    "top_k":5
  }'
```

For ordinary text questions, image evidence is excluded by default so icon
metadata does not override recall or warning-guide severity. Set
`include_image_evidence` to `true` only for icon/image-oriented questions.

Power BI Desktop can call the local API with `src/powerbi/rag_query.m`. The
local URL works on the machine running Power BI; external users need SSH/VPN
forwarding or a gateway/reverse-proxy path to reach the FastAPI service.

## Preprocessing

Raw CSV files are the local source of truth. The Python preprocessing script
generates SQL-ready processed CSV files and a reviewable `schema.json`:

```bash
python3 scripts/python/preprocess_dataset.py validate
python3 scripts/python/preprocess_dataset.py eda
python3 scripts/python/preprocess_dataset.py schema --csv-dir data/raw --output-file data/processed/schema.json
python3 scripts/python/preprocess_dataset.py clean --schema-file data/processed/schema.json
```

`schema.json` records inferred column types, preferred preprocessing types,
suggested SQL types, null-like counts, primary keys, foreign keys, and
normalization rules. It is generated from CSV files for operator review rather
than treated as the raw-data source of truth.

## Documentation
- `docs/pipeline_architecture.md`: Azure/FOSS architecture and repository
  ownership
- `docs/data_inventory.md`: provider-neutral raw data inventory
- `docs/rag_document_contract.md`: SQL RAG view and Power BI output contract
