/*
WARNY-BI query interaction log.

Run this script in the Azure SQL database used by Power BI.

This script intentionally does not preserve old logging schemas. It drops and
recreates the logging objects so the Logic App sees only the current table
shape.

The Logic App writes one row to dbo.query_log after Azure OpenAI returns:

  query_id            = guid()
  created_at_utc      = utcNow()
  pipeline            = azure_logic_app
  user_prompt         = triggerBody()?['query']
  answer_json         = choices[0].message.content
  citations_json      = choices[0].message.context.citations as JSON text
  azure_response_json = full Azure OpenAI response as JSON text

The LLM response in answer_json is the source of the parsed dashboard fields.
Azure AI Search citations are expanded by dbo.vw_query_log_evidence.
*/

SET NOCOUNT ON;
GO

DROP VIEW IF EXISTS dbo.vw_query_log_evidence;
GO

DROP VIEW IF EXISTS dbo.vw_query_log_dashboard;
GO

DROP TABLE IF EXISTS dbo.query_log_evidence;
GO

DROP TABLE IF EXISTS dbo.query_log;
GO

CREATE TABLE dbo.query_log (
    query_id UNIQUEIDENTIFIER NOT NULL,
    created_at_utc DATETIME2(3) NOT NULL,
    pipeline NVARCHAR(30) NOT NULL,
    user_prompt NVARCHAR(MAX) NOT NULL,
    answer_json NVARCHAR(MAX) NULL,
    citations_json NVARCHAR(MAX) NULL,
    azure_response_json NVARCHAR(MAX) NULL,

    CONSTRAINT PK_query_log PRIMARY KEY CLUSTERED (query_id)
);
GO

CREATE INDEX IX_query_log_created_at_utc
ON dbo.query_log (created_at_utc DESC);
GO

CREATE INDEX IX_query_log_pipeline_created_at_utc
ON dbo.query_log (pipeline, created_at_utc DESC);
GO

CREATE OR ALTER VIEW dbo.vw_query_log_dashboard
AS
SELECT
    q.query_id,
    q.created_at_utc,
    CAST(q.created_at_utc AS DATE) AS created_date_utc,
    q.pipeline,
    q.user_prompt,
    parsed.answer_summary,
    parsed.parsed_make,
    parsed.parsed_model,
    parsed.parsed_model_year,
    parsed.parsed_warning_light,
    parsed.warning_light_id,
    parsed.component_category,
    parsed.severity,
    parsed.severity_level,
    parsed.severity_color,
    parsed.severity_icon_key,
    parsed.stop_immediately,
    parsed.recommended_service,
    parsed.recall_status,
    parsed.recall_status_level,
    parsed.recall_status_color,
    parsed.recall_icon_key,
    parsed.primary_campaign,
    parsed.recall_interpretation,
    citation_stats.evidence_count,
    CASE WHEN parsed.primary_campaign IS NULL THEN 0 ELSE 1 END AS recall_candidate_count,
    CASE
        WHEN parsed.severity_level >= 4 THEN N'Immediate stop'
        WHEN parsed.severity_level = 3 THEN N'Urgent'
        WHEN parsed.severity_level = 2 THEN N'Service soon'
        ELSE N'Informational or unknown'
    END AS severity_bucket,
    CASE
        WHEN parsed.recall_status_level >= 3 THEN N'Recall candidate'
        WHEN parsed.recall_status_level = 2 THEN N'Recall review needed'
        WHEN parsed.recall_status_level = 1 THEN N'No retrieved recall candidate'
        ELSE N'Unknown'
    END AS recall_bucket,
    CASE
        WHEN parsed.stop_immediately = 1
          OR parsed.severity_level >= 4
          OR parsed.recall_status_level >= 3 THEN 1
        ELSE 0
    END AS high_impact_flag,
    q.answer_json,
    q.citations_json,
    q.azure_response_json
FROM dbo.query_log AS q
OUTER APPLY (
    SELECT
        CASE WHEN ISJSON(q.answer_json) = 1 THEN q.answer_json ELSE N'{}' END AS answer_payload,
        CASE WHEN ISJSON(q.citations_json) = 1 THEN q.citations_json ELSE N'[]' END AS citations_payload
) AS payloads
OUTER APPLY (
    SELECT
        JSON_VALUE(payloads.answer_payload, N'$.summary') AS answer_summary,
        JSON_VALUE(payloads.answer_payload, N'$.parsed.make') AS parsed_make,
        JSON_VALUE(payloads.answer_payload, N'$.parsed.model') AS parsed_model,
        TRY_CONVERT(INT, JSON_VALUE(payloads.answer_payload, N'$.parsed.model_year')) AS parsed_model_year,
        JSON_VALUE(payloads.answer_payload, N'$.parsed.warning_light') AS parsed_warning_light,
        JSON_VALUE(payloads.answer_payload, N'$.parsed.warning_light_id') AS warning_light_id,
        JSON_VALUE(payloads.answer_payload, N'$.parsed.component_category') AS component_category,
        JSON_VALUE(payloads.answer_payload, N'$.severity_label') AS severity,
        TRY_CONVERT(INT, JSON_VALUE(payloads.answer_payload, N'$.severity_level')) AS severity_level,
        JSON_VALUE(payloads.answer_payload, N'$.severity_color') AS severity_color,
        JSON_VALUE(payloads.answer_payload, N'$.severity_icon_key') AS severity_icon_key,
        CASE
            WHEN LOWER(COALESCE(JSON_VALUE(payloads.answer_payload, N'$.stop_immediately'), N'false')) IN (N'true', N'1', N'yes') THEN CONVERT(BIT, 1)
            WHEN JSON_VALUE(payloads.answer_payload, N'$.stop_immediately') IS NULL THEN NULL
            ELSE CONVERT(BIT, 0)
        END AS stop_immediately,
        JSON_VALUE(payloads.answer_payload, N'$.recommended_service') AS recommended_service,
        JSON_VALUE(payloads.answer_payload, N'$.recall_status') AS recall_status,
        TRY_CONVERT(INT, JSON_VALUE(payloads.answer_payload, N'$.recall_status_level')) AS recall_status_level,
        JSON_VALUE(payloads.answer_payload, N'$.recall_status_color') AS recall_status_color,
        JSON_VALUE(payloads.answer_payload, N'$.recall_icon_key') AS recall_icon_key,
        JSON_VALUE(payloads.answer_payload, N'$.primary_campaign') AS primary_campaign,
        JSON_VALUE(payloads.answer_payload, N'$.recall_interpretation') AS recall_interpretation
) AS parsed
OUTER APPLY (
    SELECT COUNT(*) AS evidence_count
    FROM OPENJSON(payloads.citations_payload)
) AS citation_stats;
GO

CREATE OR ALTER VIEW dbo.vw_query_log_evidence
AS
SELECT
    q.query_id,
    q.created_at_utc,
    CAST(q.created_at_utc AS DATE) AS created_date_utc,
    q.pipeline,
    q.user_prompt,
    JSON_VALUE(payloads.answer_payload, N'$.parsed.make') AS parsed_make,
    JSON_VALUE(payloads.answer_payload, N'$.parsed.model') AS parsed_model,
    TRY_CONVERT(INT, JSON_VALUE(payloads.answer_payload, N'$.parsed.model_year')) AS parsed_model_year,
    JSON_VALUE(payloads.answer_payload, N'$.parsed.warning_light') AS parsed_warning_light,
    CAST(citation.[key] AS INT) + 1 AS evidence_rank,
    COALESCE(
        NULLIF(JSON_VALUE(citation.value, N'$.chunk_id'), N''),
        NULLIF(JSON_VALUE(citation.value, N'$.filepath'), N''),
        NULLIF(JSON_VALUE(citation.value, N'$.title'), N''),
        CONCAT(N'azure-citation-', CONVERT(NVARCHAR(20), CAST(citation.[key] AS INT) + 1))
    ) AS document_id,
    N'AZURE_AI_SEARCH' AS source_type,
    N'Azure AI Search citation' AS source_type_label,
    JSON_VALUE(payloads.answer_payload, N'$.parsed.warning_light_id') AS warning_light_id,
    JSON_VALUE(payloads.answer_payload, N'$.parsed.warning_light') AS warning_light_name,
    JSON_VALUE(payloads.answer_payload, N'$.parsed.component_category') AS component_category,
    JSON_VALUE(payloads.answer_payload, N'$.severity_label') AS severity,
    JSON_VALUE(payloads.answer_payload, N'$.recommended_service') AS recommended_service,
    JSON_VALUE(payloads.answer_payload, N'$.primary_campaign') AS campaign_id,
    JSON_VALUE(payloads.answer_payload, N'$.recall_status') AS recall_status,
    JSON_VALUE(citation.value, N'$.url') AS source_url,
    LEFT(JSON_VALUE(citation.value, N'$.content'), 1000) AS content_preview,
    citation.value AS raw_citation_json
FROM dbo.query_log AS q
OUTER APPLY (
    SELECT
        CASE WHEN ISJSON(q.answer_json) = 1 THEN q.answer_json ELSE N'{}' END AS answer_payload,
        CASE WHEN ISJSON(q.citations_json) = 1 THEN q.citations_json ELSE N'[]' END AS citations_payload
) AS payloads
CROSS APPLY OPENJSON(payloads.citations_payload) AS citation;
GO

SELECT
    'query_log' AS object_name,
    COUNT(*) AS row_count
FROM dbo.query_log
UNION ALL
SELECT
    'vw_query_log_dashboard',
    COUNT(*)
FROM dbo.vw_query_log_dashboard
UNION ALL
SELECT
    'vw_query_log_evidence',
    COUNT(*)
FROM dbo.vw_query_log_evidence;
GO
