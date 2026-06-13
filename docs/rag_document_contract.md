# RAG Retrieval View

The RAG system retrieves evidence from a single SQL view:

```sql
dbo.vw_rag_documents
```

This view is built from the processed CSV-backed SQL tables. It gives Qdrant
and Azure AI Search a single, consistent source to index.

The view currently combines:

- warning-light catalog rows
- recall rows
- maintenance/service route rows
- warning-light image metadata rows
- validation scenario rows

The current local view has 585 retrievable rows.

## View Columns

| Field | Purpose |
| --- | --- |
| `document_id` | Stable ID for the retrieval row, such as `warning_light:WL062` |
| `source_type` | Original evidence type |
| `source_id` | Source record ID, such as `WL062` or `RC0002` |
| `warning_light_id` | Warning-light ID when the row is tied to a warning light |
| `warning_light_name` | Human-readable warning-light name |
| `make` | Vehicle make when the row is vehicle-specific |
| `model` | Vehicle model when the row is vehicle-specific |
| `model_year` | Vehicle model year when the row is vehicle-specific |
| `component_category` | Vehicle component or service category |
| `severity` | Warning or service urgency |
| `recommended_service_type` | Suggested service route |
| `content` | Text embedded for search and passed to the LLM as evidence |
| `source_url` | Source URL or local source marker |
| `image_path` | Image path when the row describes warning-light image metadata |
| `review_status` | Review or confidence note |

`content` is the most important field for retrieval. The remaining fields are
metadata used for filtering, citations, Power BI rows, and answer formatting.

## How Retrieval Uses The View

For a text query such as:

```text
2020 Hyundai Elantra yellow engine light recall
```

the backend should:

1. Embed the query with `mxbai-embed-large`.
2. Search Qdrant over embeddings of `vw_rag_documents.content`.
3. Retrieve matching warning-light, recall, and service-route rows.
4. Send the retrieved evidence to `qwen2.5:14b`.
5. Return a grounded answer and structured evidence rows.

The view is not the final answer. It is the evidence layer that makes the final
answer traceable.

## Power BI Output

Power BI receives one normalized response shape from either the FOSS FastAPI
pipeline or the Azure OpenAI plus Azure AI Search pipeline:

```json
{
  "query": "natural-language user prompt",
  "answer": {
    "summary": "plain-text answer summary",
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
    "possible_causes": ["Loose fuel cap", "Emissions-system fault"],
    "immediate_action": "Arrange prompt diagnostic service.",
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

`answer.summary` is the only answer-summary text field. The other answer fields
exist so cards, icons, colors, and parsed vehicle visuals can be built without
manual text parsing in Power BI.

Each evidence row should use stable display fields:

- `Query_ID`
- `document_id`
- `source_id`
- `source_type`
- `source_type_label`
- `rank`
- `score`
- `rank_score`
- `confidence_label`
- `evidence_level`
- `evidence_level_label`
- `warning_light_id`
- `warning_light_name`
- `make`
- `model`
- `model_year`
- `campaign_id`
- `recall_relevance`
- `recall_relevance_label`
- `component_category`
- `severity_label`
- `recommended_service_label`
- `source_url`
- `content_preview`

The Power Query files under `src/powerbi/` are intentionally kept small:

- `foss_query.m`: calls the local/FOSS FastAPI endpoint and returns the normalized response record.
- `azure_query.m`: calls Azure OpenAI plus Azure AI Search and returns the same normalized response record.
- `answer_query.m`: turns the normalized response into one wide, one-row answer table for dashboard cards and text visuals.
- `evidence_query.m`: turns the normalized response into one row-per-evidence table for detail tables and evidence charts.
- `log_query.m`: reads Azure SQL log views for the interaction-log page.
- `local_config.m`: reads the local, untracked Power BI configuration JSON.

Power BI visuals should bind to columns from the wide answer table and the
row-level evidence table instead of relying on many small query files.

## Prompt File

Both FOSS and Azure answer generation use `config/prompts/rag_answer.txt` as the
canonical dashboard-answer prompt.

FOSS loads that file directly. `src/powerbi/azure_query.m` contains a
fallback copy of the same instructions because a published Power BI report
cannot reliably load a repository-relative text file at refresh time.
