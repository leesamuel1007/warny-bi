# FOSS Setup

This guide sets up the local WARNY-BI system. It produces the same kind of
Power BI tables as the Azure version, but it runs with local tools instead of
Azure OpenAI and Azure AI Search.

The local pipeline is:

```text
processed CSVs -> SQL Server -> dbo.vw_rag_documents
-> OpenSearch BM25 + vector index -> Ollama -> FastAPI -> Power BI
```

Use this setup when you want to test WARNY-BI without paying for Azure model
calls. The Azure setup remains the cloud version of the project.

By the end of this guide, you should have:

- SQL Server storing the WARNY-BI CSV data.
- OpenSearch storing searchable warning-light and recall evidence.
- Ollama running the local AI models.
- FastAPI exposing a local `/query` endpoint for Power BI.
- `powerbi_dashboards/warny-bi-foss.pbix` connected to the local backend.

## Prerequisites

Install these tools locally:

- Git
- Docker
- DBeaver Community Edition
- Microsoft ODBC Driver 18 for SQL Server
- `uv`, a Python environment and dependency manager
- Ollama

Ollama must have the models named in `config/.env`. Download them with:

```bash
ollama pull mxbai-embed-large
ollama pull qwen2.5:14b
```

## Repository And Python Environment

Clone the repository and enter it:

```bash
git clone <repo-url>
cd warny-bi
```

Create a Python environment using `uv`. The commands below create a sibling
`venvs/` folder next to the repository, so the path works wherever the project
was cloned:

```bash
mkdir -p ../venvs
UV_PROJECT_ENVIRONMENT="$(pwd)/../venvs/warnybi_env" uv sync
ln -sfnT "$(pwd)/../venvs/warnybi_env" .venv
source .venv/bin/activate
```

If you keep virtual environments somewhere else, replace `../venvs/warnybi_env`
with your preferred path. Keep `.venv` as a symlink so local commands can find
the environment from the project root.

After the environment exists, future dependency syncs can be run from the
repository root with:

```bash
UV_PROJECT_ENVIRONMENT="$(readlink -f .venv)" uv sync
source .venv/bin/activate
```

## Local Services

The local system expects SQL Server, OpenSearch, and Ollama to be running.

Default local addresses:

```text
SQL Server: 127.0.0.1,1433
OpenSearch: http://127.0.0.1:9200
Ollama: http://127.0.0.1:11434
FastAPI: http://127.0.0.1:18080
```

The launcher can start existing Docker containers if their names match:

```text
SQL_CONTAINER=mssql2025
OPENSEARCH_CONTAINER=warny-opensearch
```

If your container names differ, set those environment variables before running
the launcher.

## Configuration

Create the local runtime configuration file:

```bash
cp config/.env.example config/.env
```

Edit `config/.env`. At minimum, verify these values:

```text
SQL_SERVER=127.0.0.1,1433
SQL_DATABASE=warny_bi
SQL_USER=warny_ingest
SQL_PASSWORD=<your_password_here>
OPENSEARCH_URL=http://127.0.0.1:9200
OLLAMA_URL=http://127.0.0.1:11434
API_PORT=18080
```

Do not commit `config/.env`.

## SQL Database

In DBeaver, connect to the local SQL Server and create or select the database.
The examples use this database name:

```sql
CREATE DATABASE warny_bi;
```

Run these scripts against `warny_bi`, in this order:

```text
scripts/sql/01_create_tables.sql
scripts/sql/03_create_rag_view.sql
scripts/sql/04_verify.sql
scripts/sql/05_create_query_log.sql
```

Then load the processed CSV files into SQL Server:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/python/load_to_db.py
```

If loading fails with a permission error, the SQL user in `config/.env` does
not have enough database access. Grant that user permission to insert, delete,
and select rows in the `warny_bi` database.

## Canonical Vocabulary

Build the local vocabulary file used to understand vehicle and warning-light
phrases:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/python/build_canonical_vocab.py
```

This creates `config/canonical_vocab.json`. It is generated from the CSV data
and should not be committed.

## OpenSearch And Local API

Load the SQL evidence into OpenSearch and start the local API:

```bash
scripts/bash/run_local.sh --recreate
```

Useful options:

```bash
scripts/bash/run_local.sh --load-db
scripts/bash/run_local.sh --ingest
scripts/bash/run_local.sh --recreate
```

The options mean:

- `--load-db`: reload processed CSVs into SQL and rebuild the vocabulary file.
- `--ingest`: refresh OpenSearch from SQL.
- `--recreate`: delete and recreate the OpenSearch index before refreshing it.

## Test The API

With the local API running, test it from another terminal:

```bash
curl -s -X POST http://127.0.0.1:18080/query \
  -H "Content-Type: application/json" \
  -d '{"query":"2020 Hyundai Elantra yellow engine light recall","top_k":5,"include_image_evidence":false}' | jq
```

The response should contain:

- `answer`: structured JSON for Page 1.
- `evidence`: retrieved evidence rows for Page 2.
- `rank_score`: bounded retrieval score from `0.0` to `1.0`.
- `campaign_id`: true NHTSA campaign ID when recall evidence has one.

Every successful query also writes one interaction log row to SQL with:

```text
pipeline = foss_fastapi
```

Verify logging in DBeaver:

```sql
SELECT TOP 10 *
FROM dbo.query_log
ORDER BY created_at_utc DESC;

SELECT TOP 10 *
FROM dbo.vw_query_log
ORDER BY created_at_utc DESC;
```

## Power BI

The project currently keeps separate dashboard files:

```text
powerbi_dashboards/warny-bi-foss.pbix
powerbi_dashboards/warny-bi-azure.pbix
```

Do not edit the shared Power Query files unless the dashboard owner explicitly
decides to change the expected dashboard columns.

For the FOSS dashboard, create the local Power BI configuration file:

```bash
cp config/powerbi.secrets.example.json config/powerbi.secrets.json
```

Set the active backend to `Foss`. Keep the full JSON structure from
`config/powerbi.secrets.example.json`, but make sure the `Foss` section looks
like this:

```json
{
  "ActiveBackend": "Foss",
  "Backends": {
    "Foss": {
      "RagApiUrl": "http://127.0.0.1:18080",
      "SqlServer": "127.0.0.1,1433",
      "SqlDatabase": "warny_bi"
    }
  }
}
```

Do not commit `config/powerbi.secrets.json`.

In Power BI Desktop:

1. Open `powerbi_dashboards/warny-bi-foss.pbix`.
2. Set `PowerBIProjectRoot` to the folder where this repository was cloned.
3. Set `BasePrompt`, `BaseTopK`, and `BaseIncludeImageEvidence`.
4. Refresh `Response`, `Answer`, `Evidence`, and `Log`.

Page 1 uses `Answer`, Page 2 uses `Evidence`, and Page 3 uses `Log`.

If Power BI cannot refresh:

- Confirm FastAPI is still running at `http://127.0.0.1:18080`.
- Confirm SQL Server is reachable from Power BI.
- Confirm `config/powerbi.secrets.json` exists and `ActiveBackend` is `Foss`.
- Confirm `PowerBIProjectRoot` points to the repository folder.
