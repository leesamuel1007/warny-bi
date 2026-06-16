# Azure Logic App Setup

This document records the Azure Logic App workflow used by the Azure Power BI
backend. The Logic App is the middleware between Power BI and Azure OpenAI: it
receives one natural-language prompt, calls Azure OpenAI with Azure AI Search
as the retrieval source, logs the interaction to Azure SQL, and returns the raw
Azure OpenAI response to Power BI.

Do not commit real keys, trigger URLs, or screenshots that expose secrets.

## Workflow

The Logic App contains these actions in order:

```text
Request -> RoleInformation -> HTTP -> RowInsert -> Response
```

## Prerequisites

Before configuring the Logic App, prepare these Azure resources:

- Azure OpenAI resource with a GPT-4o deployment.
- Azure AI Search service with the WARNY-BI RAG index.
- Azure SQL Database containing `dbo.query_log`.

Run the logging SQL script against the active database before configuring
`RowInsert`:

```text
scripts/sql/05_create_query_log.sql
```

## Request

Action: `When an HTTP request is received`

Use this request body schema:

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string"
    },
    "top_k": {
      "type": "integer"
    },
    "include_image_evidence": {
      "type": "boolean"
    }
  },
  "required": [
    "query"
  ]
}
```

The generated trigger URL is secret because it contains a `sig=` token. Store it
only in `config/powerbi.secrets.json` under the active backend's `RagApiUrl`.

## RoleInformation

Action: `Compose`

Action name: `RoleInformation`

Paste the full Azure prompt from:

```text
config/prompts/rag_answer_azure.txt
```

This keeps the long system prompt separate from the HTTP body and avoids JSON
escaping errors in the Logic App designer.

## HTTP

Action: `HTTP`

Method: `POST`

URI:

```text
https://<azure-openai-resource>.openai.azure.com/openai/deployments/<gpt-4o-deployment>/chat/completions?api-version=2024-05-01-preview
```

Headers:

| Header | Value |
| --- | --- |
| `Content-Type` | `application/json` |
| `api-key` | Azure OpenAI API key |

Body:

```json
{
  "messages": [
    {
      "role": "user",
      "content": "@{triggerBody()?['query']}"
    }
  ],
  "temperature": 0,
  "data_sources": [
    {
      "type": "azure_search",
      "parameters": {
        "endpoint": "<azure-ai-search-endpoint>",
        "index_name": "<azure-ai-search-index-name>",
        "authentication": {
          "type": "api_key",
          "key": "<azure-ai-search-key>"
        },
        "top_n_documents": "@{int(coalesce(triggerBody()?['top_k'], 5))}",
        "strictness": 3,
        "query_type": "simple",
        "in_scope": true,
        "role_information": "@{outputs('RoleInformation')}"
      }
    }
  ]
}
```

The `api-key` header uses the Azure OpenAI key. The
`data_sources.parameters.authentication.key` value uses the Azure AI Search key.
Do not swap these two keys.

If the designer rejects an expression pasted inside raw JSON, insert the value
through the Logic App expression editor instead of typing it as plain text.

## RowInsert

Action: SQL Server `Insert row (V2)`

Action name: `RowInsert`

Configure the SQL connection:

| Field | Value |
| --- | --- |
| Server name | Azure SQL Server host name |
| Database name | Azure SQL Database name |
| Table name | `query_log` |

Map the row values as follows:

| Column | Value |
| --- | --- |
| `query_id` | `guid()` |
| `created_at_utc` | `utcNow()` |
| `pipeline` | `azure_logic_app` |
| `user_prompt` | `triggerBody()?['query']` |
| `top_k` | `int(coalesce(triggerBody()?['top_k'], 5))` |
| `include_image_evidence` | `coalesce(triggerBody()?['include_image_evidence'], false)` |
| `answer_json` | `first(body('HTTP')?['choices'])?['message']?['content']` |
| `citations_json` | `string(first(body('HTTP')?['choices'])?['message']?['context']?['citations'])` |
| `azure_response_json` | `string(body('HTTP'))` |

If the HTTP action has a different name, replace `body('HTTP')` with that
action name.

## Response

Action: `Response`

Status code:

```text
200
```

Body:

```text
body('HTTP')
```

This returns the raw Azure OpenAI response to Power BI. The Power Query files
then normalize that response into the `Answer`, `Evidence`, and `Log` tables.

## Test

Call the Logic App trigger URL from a terminal:

```bash
curl -s -X POST "<logic-app-trigger-url>" \
  -H "Content-Type: application/json" \
  -d '{"query":"2020 Hyundai Elantra yellow engine light recall","top_k":5,"include_image_evidence":false}' | jq
```

Then verify that logging worked:

```sql
SELECT TOP 10 *
FROM dbo.query_log
ORDER BY created_at_utc DESC;

SELECT TOP 10 *
FROM dbo.vw_query_log
ORDER BY created_at_utc DESC;
```

## Power BI Configuration

For the Logic App backend, `config/powerbi.secrets.json` should select
`AzureLogicApp` and provide the Logic App trigger URL plus the SQL database used
for Page 3 logging:

```json
{
  "ActiveBackend": "AzureLogicApp",
  "Backends": {
    "AzureLogicApp": {
      "RagApiUrl": "<logic-app-trigger-url>",
      "SqlServer": "<sql-server-host>",
      "SqlDatabase": "<sql-database-name>"
    }
  }
}
```

Use `config/powerbi.secrets.example.json` as the full schema reference.
