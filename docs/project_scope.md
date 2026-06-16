# Project Scope

WARNY-BI helps users interpret vehicle dashboard warning lights with retrieved
warning-light, recall, service-route, image-metadata, and validation-scenario
evidence.

The system provides triage guidance only. It should not claim a confirmed
diagnosis, and it should point users to VIN lookup, owner manuals, OEM guidance,
or professional service inspection when needed.

## What The System Answers

- What the warning light likely means.
- How urgent the warning is.
- Whether recall evidence may be relevant.
- What service route is recommended.
- Which retrieved records support the answer.
- What warning-light and recall topics users ask about over time.

## Data Scope

The database is built from six processed CSV files:

- `dataset_sources.csv`
- `warning_light_catalog.csv`
- `maintenance_service_map.csv`
- `recall_data.csv`
- `scenario_validation.csv`
- `warning_light_image_catalog.csv`

These files are loaded into SQL Server and combined through
`dbo.vw_rag_documents` for retrieval.

## Backend Scope

Azure is the submitted cloud pipeline. FOSS is the local mirror for no-cost
testing. Both should return the same normalized Power BI response shape:

- one answer record for Page 1 cards and text
- one evidence table for Page 2 verification
- one log table for Page 3 usage analytics

Image upload and image parsing are outside the current implementation. Existing
image metadata can still be retrieved as supporting evidence.
