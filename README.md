# WARNY-BI

WARNY-BI is a DS545 project that answers vehicle dashboard warning-light
questions with retrieval-augmented generation and Power BI.

The system is not a certified diagnostic tool. It gives evidence-grounded
triage: what a warning light may mean, how urgent it is, whether recall evidence
looks relevant, what service route is recommended, and which records support the
answer.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `data/raw/` | Original source CSVs and image metadata inputs. |
| `data/processed/` | SQL-ready CSVs used to build the database. |
| `data/images/` | Warning-light image assets. |
| `scripts/sql/` | SQL Server table, retrieval-view, verification, and logging scripts. |
| `scripts/python/` | Repeatable database loading, Qdrant ingestion, and FastAPI startup scripts. |
| `scripts/bash/` | Local FOSS launcher. |
| `scripts/powerbi/` | Power Query M files for Power BI Desktop. |
| `src/warnybi/` | Local FOSS RAG backend using SQL Server, Qdrant, Ollama, and FastAPI. |
| `config/prompts/` | Azure and FOSS RAG prompt templates. |
| `docs/` | Human-readable architecture, data, and RAG contract notes. |

## Current Pipelines

The Azure path used for the final dashboard was:

```text
processed CSVs -> Azure SQL -> dbo.vw_rag_documents -> Azure AI Search
-> Azure OpenAI GPT-4o -> Logic App -> Power BI
```

The local FOSS path mirrors that contract:

```text
processed CSVs -> SQL Server -> dbo.vw_rag_documents -> Qdrant
-> Ollama -> FastAPI -> Power BI
```

Both paths use the same Power BI-facing response shape and the same SQL log
view:

```text
dbo.query_log
dbo.vw_query_log
```

Azure log rows use `pipeline = azure_logic_app`. Local FOSS log rows use
`pipeline = foss_fastapi`.

The detailed Azure Logic App setup is recorded in
`docs/logic_app_setup.md`.

## Local FOSS Setup

Create `config/.env` from `config/.env.example` and fill in the SQL password.
The default local services are:

- SQL Server: `127.0.0.1,1433`
- Qdrant: `http://127.0.0.1:16333`
- Ollama: `http://127.0.0.1:11434`
- FastAPI: `http://127.0.0.1:18080`

Run the SQL scripts in DBeaver against the target SQL database:

```text
scripts/sql/01_create_tables.sql
scripts/sql/03_create_rag_view.sql
scripts/sql/04_verify.sql
scripts/sql/05_create_query_log.sql
```

Load the processed CSVs with the ODBC loader:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/python/load_to_db.py
```

This loader is the repeatable replacement for manual DBeaver CSV import. It can
also target Azure SQL in principle if the Azure server, firewall, credentials,
and ODBC driver are available, but the Azure SQL server used for the project has
been purged and is not currently verified.

Refresh Qdrant from the SQL retrieval view:

```bash
UV_CACHE_DIR=/tmp/uv-cache uv run python scripts/python/load_to_qdrant.py --recreate
```

Start the local API:

```bash
scripts/bash/run_local_foss_api.sh
```

Useful launcher options:

```bash
scripts/bash/run_local_foss_api.sh --load-db
scripts/bash/run_local_foss_api.sh --ingest
scripts/bash/run_local_foss_api.sh --recreate
```

Test the API:

```bash
curl -s -X POST http://127.0.0.1:18080/query \
  -H "Content-Type: application/json" \
  -d '{"query":"2020 Hyundai Elantra yellow engine light recall","top_k":5}' | jq
```

## FOSS Query Logging

Local FOSS logging is mandatory after `05_create_query_log.sql` has been run.
Every successful `/query` call inserts one row into `dbo.query_log` with
`pipeline = foss_fastapi`, matching the Azure Logic App logging contract.

If logging fails, the `/query` request fails after the configured retry attempts
and the FastAPI terminal shows the SQL error. This usually means the SQL Server
is unreachable, the configured SQL user does not have insert permission on
`dbo.query_log`, `05_create_query_log.sql` was not run, or the database schema
does not match the current scripts.

Retry settings are configured in `config/.env`:

```text
RETRY_ATTEMPTS=3
RETRY_DELAY_SEC=0.5
```

## Power BI Setup

Create a local untracked file from the example:

```text
config/powerbi.secrets.example.json -> config/powerbi.secrets.json
```

Open `config/powerbi.secrets.json`, set `ActiveBackend`, and fill in only the
backend section you plan to use. The example file is the source of truth for the
required JSON shape.

`ActiveBackend` selects the record returned by `LoadConfig`. Supported backend
sections are:

- `AzureLogicApp`: Power BI calls the Logic App URL. Azure OpenAI and Azure AI
  Search keys stay inside Azure, not inside the PBIX.
- `Foss`: Power BI calls the local FastAPI URL.
- `AzureDirect`: stores the secrets needed for a direct Power BI to Azure
  OpenAI call. This is not the current shared `Response` flow unless a direct
  Azure Power Query implementation is used.

`SqlServer` and `SqlDatabase` point to the database that contains
`dbo.vw_query_log`.

In Power BI Desktop, create these queries from `scripts/powerbi/`:

| Power BI query | Source file | Enable load |
| --- | --- | --- |
| `LoadConfig` | `load_config.m` | No |
| `Query` | `azure_query.m` or `foss_query.m` | No |
| `Response` | `response_query.m` | No |
| `Answer` | `answer_query.m` | Yes |
| `Evidence` | `evidence_query.m` | Yes |
| `Log` | `log_query.m` | Yes |

Use `azure_query.m` or `foss_query.m` as the implementation of the Power BI
query named `Query`. Both use `RagApiUrl`, so `Response` and `Log` remain
backend-agnostic. If `ActiveBackend` is `AzureDirect`, use or create a direct
Azure query implementation that reads the Azure OpenAI and Azure AI Search
fields returned by `LoadConfig`.

Required Power BI parameters:

| Parameter | Type | Purpose |
| --- | --- | --- |
| `PowerBIProjectRoot` | Text | Local repository path. |
| `BasePrompt` | Text | Natural-language prompt sent to the backend. |
| `BaseTopK` | Whole Number | Number of retrieved evidence rows. |
| `BaseIncludeImageEvidence` | True/False | Whether image metadata can be retrieved. |

## Secrets

Do not commit:

- `config/.env`
- `config/powerbi.secrets.json`
- Logic App URLs with `sig=`
- Azure keys, SQL passwords, SAS tokens, or connection strings

The checked-in example files show the required fields without real values.
