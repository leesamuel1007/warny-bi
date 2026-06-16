# RAG And Power BI Contract

The retrieval source is:

```sql
dbo.vw_rag_documents
```

The interaction log source is:

```sql
dbo.vw_query_log
```

## Retrieval View

`dbo.vw_rag_documents` combines warning-light, recall, service-route,
image-metadata, and validation-scenario rows into one retrievable view.

Important fields:

| Field | Purpose |
| --- | --- |
| `search_key` | Azure AI Search-safe key. |
| `document_id` | Stable evidence ID such as `recall:RC0002`. |
| `source_type` | Evidence source category. |
| `warning_light_id` | Warning-light ID when available. |
| `make`, `model`, `model_year` | Vehicle context when available. |
| `severity` | Urgency signal from the source data. |
| `recommended_service_type` | Controlled service route token. |
| `content` | Text embedded and passed to the LLM as evidence. |
| `source_url` | Source reference. |
| `image_path` | Local or blob path for image metadata rows. |

The local verified retrieval view contains 585 rows.

## API Response Shape

Azure and FOSS both normalize responses into this shape for Power BI:

```json
{
  "query": "natural-language prompt",
  "top_k": 5,
  "include_image_evidence": false,
  "answer": {
    "summary": "Plain-language summary",
    "severity_label": "Service soon",
    "severity_level": 2,
    "severity_color": "#F2C94C",
    "severity_icon_key": "service_soon",
    "stop_immediately": false,
    "recommended_service": "Engine/emissions diagnostic",
    "recall_status": "Candidate recall match",
    "recall_status_level": 3,
    "recall_status_color": "#7B1FA2",
    "recall_icon_key": "recall_candidate",
    "possible_causes": ["Loose fuel cap"],
    "immediate_action": "Schedule prompt diagnostic service.",
    "primary_campaign": "21V301000",
    "recall_interpretation": "VIN confirmation is required.",
    "evidence_used": ["recall:RC0002"],
    "parsed": {
      "make": "Hyundai",
      "model": "Elantra",
      "model_year": 2020,
      "warning_light": "engine light",
      "warning_light_id": "WL062",
      "component_category": "Engine/emissions"
    }
  },
  "evidence": []
}
```

Power BI uses:

- `Answer` for Page 1 triage cards and text.
- `Evidence` for Page 2 recall/evidence inspection.
- `Log` for Page 3 historical usage analytics.

## Power BI Backend Config

`scripts/powerbi/load_config.m` reads `config/powerbi.secrets.json`, selects
the record named by `ActiveBackend`, and returns that selected backend record to
the other Power Query files.

`AzureLogicApp` and `Foss` both expose:

- `RagApiUrl`
- `SqlServer`
- `SqlDatabase`

That is why `Response` and `Log` do not need backend-specific branches.

`AzureDirect` stores direct Azure OpenAI and Azure AI Search fields. It is for a
direct Azure Power Query implementation, not the current Logic App-mediated
`azure_query.m`.

## Prompt Files

- `config/prompts/rag_answer_azure.txt`: Azure Logic App role information.
- `config/prompts/rag_answer_foss.txt`: FOSS answer-generation prompt. The
  local backend inserts the natural-language query and retrieved evidence into
  this single prompt.

Azure receives retrieved evidence through Azure AI Search. FOSS retrieves
evidence from Qdrant and inserts it into the local prompt.
