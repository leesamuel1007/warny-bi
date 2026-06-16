# Data Inventory

WARNY-BI uses CSV records and warning-light image assets.

## Processed CSV Files

`data/processed/` is the current database-load source.

| File | SQL table | Role |
| --- | --- | --- |
| `dataset_sources.csv` | `dataset_sources` | Source and license metadata. |
| `warning_light_catalog.csv` | `warning_light_catalog` | Main warning-light guidance. |
| `maintenance_service_map.csv` | `maintenance_service_map` | Service route and urgency mapping. |
| `recall_data.csv` | `recall_data` | Vehicle recall evidence. |
| `scenario_validation.csv` | `scenario_validation` | Test cases and expected behavior. |
| `warning_light_image_catalog.csv` | `warning_light_image_catalog` | Warning-light image metadata. |

Load these files with:

```bash
uv run python scripts/python/load_to_db.py
```

## Raw Data And Images

`data/raw/` contains original source CSVs retained for traceability.
`data/images/` contains warning-light image files grouped by warning-light
class folders.

The SQL tables store image paths and metadata, not image binaries.

## Retrieval Use

After the six SQL tables are loaded, `scripts/sql/03_create_rag_view.sql`
creates `dbo.vw_rag_documents`. This view contains the text and metadata that
Azure AI Search or Qdrant indexes for RAG retrieval.
