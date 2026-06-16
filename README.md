# WARNY-BI

WARNY-BI is a vehicle warning-light triage project built with Power BI and
retrieval-augmented generation. The Power BI dashboard searches a small
warning-light and recall knowledge base, asks an AI model to write a structured
answer from the retrieved records, and displays the result.

The dashboard answers driver questions such as:

```text
2020 Hyundai Elantra yellow engine light recall
```

It returns warning-light severity, stop/service guidance, recommended service,
recall status, possible causes, immediate action, parsed vehicle information,
and supporting evidence.

WARNY-BI is not a certified diagnostic tool. It is an evidence-grounded
dashboard prototype for warning-light and recall triage.

## Collaborators And Maintainers

Project collaborators:

- Sejun Ahn: GSDS
- Fatima M. Ali: GSDS
- Samuel S. Lee: GSC
- Yongmin Kim: GSCEE

Project maintainers:

- Samuel S. Lee: leesamuel1007@kaist.ac.kr

## Dashboard Pages

The Power BI dashboard has three pages:

1. Driver Triage: concise driver-facing answer, severity, recall status,
   recommended service, causes, and immediate action.
2. Recall And Evidence: retrieved recall, warning-light, service-map, and
   validation evidence for checking whether the answer is supported.
3. Interaction Logging: previous user prompts and usage summaries for business
   and product analysis.

Dashboard screenshots used in the report are stored under `docs/`, especially:

```text
docs/report_figures/
```

The dashboard files themselves are in `powerbi_dashboards/`.

## Repository Layout

| Path | Purpose |
| --- | --- |
| `data/processed/` | SQL-ready CSV files used to populate the database. |
| `data/raw/` | Original project data inputs. |
| `data/images/` | Warning-light image assets. |
| `scripts/sql/` | SQL scripts that create the database tables, search view, checks, and query log. |
| `scripts/python/` | Python commands for loading data, building local search files, refreshing OpenSearch, and starting the local API. |
| `scripts/bash/` | One-command local launcher. |
| `scripts/powerbi/` | Shared Power Query M files used inside the dashboards. Avoid editing them unless the dashboard columns are intentionally changed. |
| `src/warnybi/` | Local FOSS system code. |
| `config/prompts/` | Azure and FOSS RAG prompts. |
| `powerbi_dashboards/` | Power BI dashboard files. |
| `docs/` | Setup guides and report figures. |

## Azure Pipeline

The Azure version uses managed cloud services. Its flow is:

```text
processed CSVs -> Azure SQL Database -> dbo.vw_rag_documents
-> Azure AI Search -> Azure OpenAI GPT-4o
-> Azure Logic App -> Power BI
```

The Logic App is the middle step between Power BI and Azure OpenAI. It receives
Power BI prompts, calls Azure OpenAI with Azure AI Search as the search source,
writes interaction logs to Azure SQL, and returns the answer to Power BI.

Use this guide:

```text
docs/azure_setup.md
```

The Logic App instructions are included in `docs/azure_setup.md`.

## FOSS Pipeline

The FOSS version is the local, no-cloud alternative. Its flow is:

```text
processed CSVs -> SQL Server -> dbo.vw_rag_documents
-> OpenSearch BM25 + vector index -> Ollama
-> FastAPI -> Power BI
```

The FOSS version returns the same kind of answer and evidence tables as Azure.
It uses OpenSearch for local search, Ollama for local AI models, FastAPI for
the local web API, and the same SQL logging table/view used by the Azure
dashboard.

Use this guide:

```text
docs/foss_setup.md
```

## Power BI Dashboards

The repository currently keeps two dashboard files:

```text
powerbi_dashboards/warny-bi-azure.pbix
powerbi_dashboards/warny-bi-foss.pbix
```

The Power Query files under `scripts/powerbi/` are shared by both dashboards.
Do not edit them unless the expected dashboard columns are intentionally
changed.

Both dashboards use:

- `LoadConfig`
- `Query`
- `Response`
- `Answer`
- `Evidence`
- `Log`

Power BI reads local connection settings from this ignored file:

```text
config/powerbi.secrets.json
```

Create it from:

```text
config/powerbi.secrets.example.json
```

Set `ActiveBackend` to the dashboard you are using:

- `AzureLogicApp` for `warny-bi-azure.pbix`
- `Foss` for `warny-bi-foss.pbix`

In Power BI Desktop, set these parameters:

| Parameter | Purpose |
| --- | --- |
| `PowerBIProjectRoot` | Local repository path. |
| `BasePrompt` | User prompt sent to the backend. |
| `BaseTopK` | Number of evidence rows to retrieve. |
| `BaseIncludeImageEvidence` | Whether image metadata can be retrieved. |

After changing the prompt or backend settings, refresh `Response`, `Answer`,
`Evidence`, and `Log`.
