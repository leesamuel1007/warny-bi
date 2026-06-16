# Pipeline Architecture

WARNY-BI has two interchangeable RAG backends.

## Azure Logic App Backend

```text
processed CSVs
-> Azure SQL Database
-> dbo.vw_rag_documents
-> Azure AI Search
-> Azure OpenAI GPT-4o
-> Azure Logic App
-> Power BI
```

The Azure backend was used for the final submitted dashboard. The Logic App
receives one natural-language prompt, calls Azure OpenAI with Azure AI Search as
the retrieval source, writes one row to `dbo.query_log`, and returns the raw
Azure OpenAI response to Power BI.

Power BI only needs the Logic App trigger URL for this backend. Azure OpenAI
and Azure AI Search keys stay in Azure.

## Azure Direct Backend

The Power BI configuration also has an `AzureDirect` section for a direct Power
BI to Azure OpenAI/Azure AI Search call. That path requires Azure OpenAI and
Azure AI Search endpoint/key fields in the local Power BI secrets file and a
direct Azure Power Query implementation. It is separate from the Logic App
backend.

## Local FOSS Backend

```text
processed CSVs
-> local SQL Server
-> dbo.vw_rag_documents
-> Qdrant
-> Ollama
-> FastAPI
-> Power BI
```

The FOSS backend is the free local test path. It uses the same SQL retrieval
view and the same Power BI response shape as Azure. Successful queries write
rows to the same `dbo.query_log` table with `pipeline = foss_fastapi`.

## Shared SQL Contract

Both backends depend on these SQL objects:

- `dbo.vw_rag_documents`: retrieval records for vector search.
- `dbo.query_log`: one row per RAG interaction.
- `dbo.vw_query_log`: Power BI-ready log view for Page 3 analytics.

Run SQL scripts against the intended active database in this order:

```text
01_create_tables.sql
03_create_rag_view.sql
04_verify.sql
05_create_query_log.sql
```

Load processed CSVs with:

```bash
uv run python scripts/python/load_to_db.py
```

## Runtime Components

- `src/warnybi/`: local RAG service code.
- `scripts/python/load_to_db.py`: processed CSV to SQL loader.
- `scripts/python/load_to_qdrant.py`: SQL retrieval view to Qdrant ingestion.
- `scripts/python/run_rag_api.py`: FastAPI service runner.
- `scripts/bash/run_local_foss_api.sh`: local launcher.
- `scripts/powerbi/`: Power Query files used in Power BI Desktop.

## Power BI Backend Selection

`config/powerbi.secrets.json` selects one backend with `ActiveBackend`.
`LoadConfig` returns the selected backend record. The shared `Response` and
`Log` queries stay backend-agnostic as long as the selected backend exposes
`RagApiUrl`, `SqlServer`, and `SqlDatabase`.
