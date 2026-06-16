# Azure Setup

This guide describes the Azure WARNY-BI system used by the Azure Power BI
dashboard.

The Azure pipeline is:

```text
processed CSVs -> Azure SQL Database -> dbo.vw_rag_documents
-> Azure AI Search -> Azure OpenAI GPT-4o
-> Azure Logic App -> Power BI
```

The Logic App is the connector between Power BI and Azure OpenAI. Power BI sends
one user prompt to the Logic App. The Logic App asks Azure OpenAI to answer
using Azure AI Search evidence, saves the interaction to Azure SQL, and returns
the answer to Power BI.

Do not commit real Azure keys, SQL passwords, Logic App trigger URLs, or
screenshots that expose secrets.

## Azure Resources

Create or prepare these resources:

- Resource group.
- Azure SQL Server and Azure SQL Database.
- Azure OpenAI resource with a GPT-4o deployment.
- Azure AI Search service with the WARNY-BI RAG index.
- Azure Logic App.

The project was built from processed CSV tables. Azure SQL was used to create a
single retrieval view before indexing into Azure AI Search.

Keep a note of these values while setting up Azure:

| Value | Used for |
| --- | --- |
| Azure SQL Server name | Power BI logging connection and Logic App SQL action. |
| Azure SQL Database name | Power BI logging connection and Logic App SQL action. |
| Azure OpenAI endpoint | Logic App HTTP action. |
| GPT-4o deployment name | Logic App HTTP action. |
| Azure OpenAI key | Logic App HTTP header. |
| Azure AI Search endpoint | Logic App data source. |
| Azure AI Search index name | Logic App data source. |
| Azure AI Search key | Logic App data source authentication. |
| Logic App trigger URL | Power BI `RagApiUrl`. |

## Azure SQL Database

Connect to the Azure SQL Database from DBeaver. If DBeaver cannot connect, add
your current client IP address to the Azure SQL Server firewall rules in the
Azure Portal.

Run the table and view scripts against the target database, in this order:

```text
scripts/sql/01_create_tables.sql
scripts/sql/03_create_rag_view.sql
scripts/sql/04_verify.sql
scripts/sql/05_create_query_log.sql
```

`01_create_tables.sql` creates the processed-data tables.
`03_create_rag_view.sql` creates `dbo.vw_rag_documents`, the shared retrieval
surface. `05_create_query_log.sql` creates the interaction log table and the
Power BI-friendly logging view.

Load the processed CSVs from `data/processed/` into the Azure SQL tables.
DBeaver import can be used manually. The local ODBC loader can also be adapted
if the Azure SQL server, firewall, ODBC driver, and credentials are available.

Verify the database:

```sql
SELECT COUNT(*) AS row_count
FROM dbo.vw_rag_documents;

SELECT TOP 10 *
FROM dbo.vw_rag_documents
ORDER BY document_id;
```

## Azure AI Search

Create an Azure AI Search service and build an index over
`dbo.vw_rag_documents`. This index is what Azure OpenAI searches before writing
an answer.

Recommended index behavior:

- Use the SQL view as the retrieval source.
- Include text fields such as `content`, `warning_light_name`, `make`,
  `model`, `component_category`, `source_type`, and `warning_light_id`.
- Keep document metadata fields available for citations.
- Use the same index name in the Logic App HTTP body.

The project report figures under `docs/report_figures/` include screenshots of
the Azure AI Search index and related Azure resources.

## Azure OpenAI

Create a GPT-4o deployment in the Azure OpenAI resource.

The Logic App HTTP action calls:

```text
https://<azure-openai-resource>.openai.azure.com/openai/deployments/<gpt-4o-deployment>/chat/completions?api-version=2024-05-01-preview
```

The Azure answer prompt is stored in:

```text
config/prompts/rag_answer_azure.txt
```

That prompt instructs GPT-4o to return one structured JSON object for the Power
BI dashboard. The dashboard expects that JSON structure, so do not casually
change the prompt keys.

## Test In Azure AI Foundry

Before connecting Power BI, test the search-and-answer behavior in Azure AI
Foundry Chat Playground:

1. Select the GPT-4o deployment.
2. Attach the Azure AI Search index as the data source.
3. Paste the contents of `config/prompts/rag_answer_azure.txt` as the system or
   role information prompt.
4. Test prompts with different levels of specificity.
5. Confirm at least one answer against the source CSV/SQL record.

Example prompt:

```text
2020 Hyundai Elantra yellow engine light recall
```

The response should contain fields such as `summary`,
`severity_level`, `recommended_service`, `recall_status`, `primary_campaign`,
`evidence_used`, and `parsed`.

## Logic App Workflow

Create the Logic App with these actions in order:

```text
Request -> RoleInformation -> HTTP -> RowInsert -> Response
```

### Request

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

The generated trigger URL contains a `sig=` token and is secret. Store it only
in local `config/powerbi.secrets.json`.

### RoleInformation

Action: `Compose`

Action name: `RoleInformation`

Paste the full prompt from:

```text
config/prompts/rag_answer_azure.txt
```

Using a Compose action keeps the long prompt separate from the HTTP JSON body.
This makes the Logic App easier to edit and reduces copy-paste errors.

### HTTP

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

The HTTP header `api-key` is the Azure OpenAI key. The
`data_sources.parameters.authentication.key` value is the Azure AI Search key.
Do not swap them.

If the Logic App designer rejects an expression pasted inside raw JSON, insert
the value through the expression editor instead.

### RowInsert

Action: SQL Server `Insert row (V2)`

Action name: `RowInsert`

Configure the SQL connection:

| Field | Value |
| --- | --- |
| Server name | Azure SQL Server host name |
| Database name | Azure SQL Database name |
| Table name | `query_log` |

Map these row values:

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
action name in the expressions.

### Response

Action: `Response`

Status code:

```text
200
```

Body:

```text
body('HTTP')
```

Power BI normalizes this Azure OpenAI response into `Response`, `Answer`,
`Evidence`, and `Log`.

## Test The Logic App

Call the generated trigger URL:

```bash
curl -s -X POST "<logic-app-trigger-url>" \
  -H "Content-Type: application/json" \
  -d '{"query":"2020 Hyundai Elantra yellow engine light recall","top_k":5,"include_image_evidence":false}' | jq
```

Then verify that the Logic App wrote a row to SQL:

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
powerbi_dashboards/warny-bi-azure.pbix
powerbi_dashboards/warny-bi-foss.pbix
```

Do not edit the shared Power Query files unless the dashboard owner explicitly
decides to change the expected dashboard columns.

For the Azure dashboard, create the local Power BI configuration file:

```bash
cp config/powerbi.secrets.example.json config/powerbi.secrets.json
```

Set the active backend to `AzureLogicApp`. Keep the full JSON structure from
`config/powerbi.secrets.example.json`, but make sure the `AzureLogicApp`
section looks like this:

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

Do not commit `config/powerbi.secrets.json`.

In Power BI Desktop:

1. Open `powerbi_dashboards/warny-bi-azure.pbix`.
2. Set `PowerBIProjectRoot` to the folder where this repository was cloned.
3. Set `BasePrompt`, `BaseTopK`, and `BaseIncludeImageEvidence`.
4. Refresh `Response`, `Answer`, `Evidence`, and `Log`.

Page 1 uses `Answer`, Page 2 uses `Evidence`, and Page 3 uses `Log`.

If Power BI cannot refresh:

- Confirm the Logic App trigger URL works with the curl test.
- Confirm the Azure SQL credentials in Power BI can read `dbo.vw_query_log`.
- Confirm `config/powerbi.secrets.json` exists and `ActiveBackend` is
  `AzureLogicApp`.
- Confirm `PowerBIProjectRoot` points to the repository folder.
