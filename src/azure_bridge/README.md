# WARNY-BI Azure Bridge

This folder contains the Azure Functions bridge used when the Power BI dashboard
must log user interactions automatically.

The bridge replaces direct Power Query calls to Azure OpenAI:

```text
Power BI -> Azure Function /api/query
          -> Azure OpenAI GPT-4o with Azure AI Search
          -> Azure SQL dbo.query_log and dbo.query_log_evidence
```

The function returns the same normalized `query`, `answer`, and `evidence`
record shape used by the local FOSS API, so the shared Power Query answer and
evidence functions can stay backend-neutral.

## Endpoints

- `GET /api/health`
- `POST /api/query`

Request body:

```json
{
  "query": "2020 Hyundai Elantra yellow engine light recall",
  "top_k": 5,
  "include_image_evidence": false
}
```

## Required App Settings

Set these in the Azure Function App configuration. Do not commit real secrets.

- `WARNY_AZURE_OPENAI_ENDPOINT`
- `WARNY_AZURE_OPENAI_KEY`
- `WARNY_AZURE_CHAT_DEPLOYMENT`
- `WARNY_AZURE_SEARCH_ENDPOINT`
- `WARNY_AZURE_SEARCH_KEY`
- `WARNY_AZURE_SEARCH_INDEX`
- `SqlConnectionString`
- `WARNY_QUERY_LOG_ENABLED=true`

Optional settings:

- `WARNY_AZURE_OPENAI_API_VERSION=2024-05-01-preview`
- `WARNY_AZURE_TOP_K=5`
- `WARNY_AZURE_STRICTNESS=3`
- `WARNY_AZURE_QUERY_TYPE=simple`
- `WARNY_AZURE_SEMANTIC_CONFIGURATION`
- `WARNY_AZURE_EMBEDDING_DEPLOYMENT`
- `WARNY_AZURE_FILTER`
- `WARNY_ROLE_INFORMATION_PATH`
- `WARNY_ROLE_INFORMATION`
- `WARNY_QUERY_LOG_PIPELINE=azure`

Run `scripts/sql/05_create_query_log.sql` in Azure SQL before enabling logging.

The SQL writes use Azure Functions Azure SQL output bindings, so the function
app needs the extension bundle in `host.json`. The code does not require
`pyodbc` or an ODBC driver.
