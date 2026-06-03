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

Power BI should receive structured rows that can be grouped and charted. The LLM
should not be responsible for dashboard aggregation.

Recommended output fields:

- `Query_ID`
- `Vehicle_Make`
- `Vehicle_Model`
- `Model_Year`
- `Warning_Light`
- `Severity`
- `Component`
- `Immediate_Action`
- `Recall_Relevance`
- `Recommended_Service`
- `Evidence_Level`
- `Source_Type`
- `Source_ID`
- `Evidence_Text`
- `Retrieval_Score`
