# WARNY-BI Data Inventory

This document is the durable, provider-neutral inventory for raw WARNY-BI data.

Raw CSV datasets live under `term_project/data/raw/`. Warning-light image files
live under `term_project/data/images/`. These source assets are shared by both
the Azure and FOSS paths.

Generated processed CSV files live under `term_project/data/processed/`. They
are SQL-ready outputs created by `scripts/python/preprocess_dataset.py`, not
raw source data.

## CSV Sources

| Source file | Rows incl. header | Shared role | Suggested clean entity |
| --- | ---: | --- | --- |
| `data/raw/dataset_sources.csv` | 8 | Source, license, and collection metadata | `dataset_sources` |
| `data/raw/warning_light_catalog.csv` | 65 | Main warning-light evidence records | `warning_light_catalog` |
| `data/raw/warning_light_image_catalog.csv` | 303 | Image-to-warning-light mapping | `warning_light_images` |
| `data/raw/recall_data.csv` | 166 | NHTSA recall evidence | `recalls` |
| `data/raw/maintenance_service_map.csv` | 35 | Service-category and urgency mapping | `maintenance_services` |
| `data/raw/scenario_validation.csv` | 21 | Expected behavior test cases | `validation_scenarios` |

## Image Sources

- Root: `data/images/`
- Current count: 302 files
- Current class folders: 64
- Current catalog path convention: CSV values use project-relative
  `data/images/...` paths.

Images are shared source assets. Azure should normally store them in Blob
Storage, while FOSS may read them from the local filesystem or object storage.
Relational/vector records should store image metadata and paths, not image
binary content.

## How The Data Is Used

Python reads the raw CSV files, performs lightweight validation and EDA,
generates `schema.json` for operator review, and writes processed CSV files.
Azure and FOSS SQL scripts should build relational database tables from the
processed CSV files. The RAG-readable retrieval surface should be a SQL view,
not a Python-generated document file.

Image binary content is treated as a source asset. SQL/vector records should
store image metadata and image paths or blob paths, not image binary content.
