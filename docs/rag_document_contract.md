# SQL RAG View Contract

Azure and FOSS pipelines should expose a single SQL view for retrieval. Azure
AI Search can index this view directly or through an export step, and the FOSS
pipeline can export the same view into a local vector store.

The view should be built from processed CSV-backed SQL tables, not from a
Python-generated retrieval file.

| Field | Purpose |
| --- | --- |
| `document_id` | Stable unique ID for the retrievable row |
| `source_type` | Warning light, recall, maintenance map, image metadata, or scenario |
| `source_id` | Original source key, such as `WL062` or `RC0002` |
| `warning_light_id` | Standard warning-light ID when applicable |
| `warning_light_name` | Human-readable warning-light name |
| `make` | Vehicle make when applicable |
| `model` | Vehicle model when applicable |
| `model_year` | Vehicle model year when applicable |
| `component_category` | Vehicle component or service category |
| `severity` | Urgency/severity label |
| `recommended_service_type` | Service routing label |
| `content` | Searchable text used for retrieval and grounding |
| `source_url` | Source URL or local-source marker |
| `image_path` | Provider-neutral image path or blob path when applicable |
| `review_status` | Source/review confidence state |

## Power BI Output

Power BI should receive structured evidence rows with stable columns. Counting,
grouping, and chart aggregation should happen in Power BI, not in the LLM.

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
