/*
WARNY-BI query interaction log.

Run this script in the Azure SQL database used by Power BI.

This script intentionally does not preserve old logging schemas. It drops and
recreates the logging objects so Power BI sees only the current table shape.

Each RAG pipeline writes one row to dbo.query_log after an answer returns.
The current Azure path writes from the Logic App. The FOSS path should write the
same fields from the FastAPI backend when local logging is enabled.

  query_id            = guid()
  created_at_utc      = utcNow()
  pipeline            = azure_logic_app or foss_fastapi
  user_prompt         = original natural-language prompt
  answer_json         = structured dashboard answer JSON
  citations_json      = evidence/citations as JSON text
  azure_response_json = full upstream response JSON when available

The LLM response in answer_json is the source of the parsed dashboard fields.
The citations_json payload is expanded by dbo.vw_query_log.
*/

SET NOCOUNT ON;
GO

DROP VIEW IF EXISTS dbo.vw_query_log_dashboard;
GO

DROP VIEW IF EXISTS dbo.vw_query_log_evidence;
GO

DROP VIEW IF EXISTS dbo.vw_query_log;
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

CREATE OR ALTER VIEW dbo.vw_query_log
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
    parsed.possible_causes,
    parsed.immediate_action,
    parsed.evidence_used,
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
    CASE
        WHEN citation.[key] IS NULL THEN NULL
        ELSE CAST(citation.[key] AS INT) + 1
    END AS evidence_rank,
    COALESCE(
        NULLIF(citation_fields.document_id, N''),
        citation_content.document_id,
        CASE WHEN NULLIF(citation_fields.chunk_id, N'') <> N'0' THEN NULLIF(citation_fields.chunk_id, N'') END,
        NULLIF(citation_fields.filepath, N''),
        NULLIF(citation_fields.title, N''),
        CASE
            WHEN citation.[key] IS NULL THEN NULL
            ELSE CONCAT(N'citation-', CONVERT(NVARCHAR(20), CAST(citation.[key] AS INT) + 1))
        END
    ) AS evidence_document_id,
    COALESCE(
        NULLIF(citation_fields.source_type, N''),
        citation_content.source_type,
        N'RAG_EVIDENCE'
    ) AS evidence_source_type,
    COALESCE(
        NULLIF(citation_fields.source_type_label, N''),
        NULLIF(citation_fields.source_type, N''),
        citation_content.source_type,
        N'RAG evidence'
    ) AS evidence_source_type_label,
    COALESCE(
        NULLIF(citation_fields.warning_light_id, N''),
        parsed.warning_light_id
    ) AS evidence_warning_light_id,
    COALESCE(
        NULLIF(citation_fields.warning_light_name, N''),
        parsed.parsed_warning_light
    ) AS evidence_warning_light_name,
    COALESCE(
        NULLIF(citation_fields.component_category, N''),
        parsed.component_category
    ) AS evidence_component_category,
    COALESCE(
        NULLIF(citation_fields.severity, N''),
        parsed.severity
    ) AS evidence_severity,
    COALESCE(
        NULLIF(citation_fields.recommended_service, N''),
        NULLIF(citation_fields.recommended_service_type, N''),
        parsed.recommended_service
    ) AS evidence_recommended_service,
    COALESCE(
        NULLIF(citation_fields.campaign_id, N''),
        parsed.primary_campaign
    ) AS evidence_campaign_id,
    COALESCE(
        NULLIF(citation_fields.recall_status, N''),
        NULLIF(citation_fields.recall_relevance, N''),
        parsed.recall_status
    ) AS evidence_recall_status,
    COALESCE(
        NULLIF(citation_fields.url, N''),
        NULLIF(citation_fields.source_url, N'')
    ) AS evidence_source_url,
    LEFT(
        COALESCE(
            NULLIF(citation_fields.content_preview, N''),
            NULLIF(citation_fields.content, N'')
        ),
        1000
    ) AS evidence_content_preview,
    citation.value AS evidence_raw_json,
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
        JSON_VALUE(payloads.answer_payload, N'$.recall_interpretation') AS recall_interpretation,
        JSON_QUERY(payloads.answer_payload, N'$.possible_causes') AS possible_causes,
        JSON_VALUE(payloads.answer_payload, N'$.immediate_action') AS immediate_action,
        JSON_QUERY(payloads.answer_payload, N'$.evidence_used') AS evidence_used
) AS parsed
OUTER APPLY (
    SELECT COUNT(*) AS evidence_count
    FROM OPENJSON(payloads.citations_payload)
) AS citation_stats
OUTER APPLY OPENJSON(payloads.citations_payload) AS citation
OUTER APPLY OPENJSON(citation.value)
WITH (
    content NVARCHAR(MAX) N'$.content',
    content_preview NVARCHAR(1000) N'$.content_preview',
    document_id NVARCHAR(160) N'$.document_id',
    chunk_id NVARCHAR(4000) N'$.chunk_id',
    filepath NVARCHAR(4000) N'$.filepath',
    title NVARCHAR(4000) N'$.title',
    source_type NVARCHAR(255) N'$.source_type',
    source_type_label NVARCHAR(255) N'$.source_type_label',
    warning_light_id NVARCHAR(50) N'$.warning_light_id',
    warning_light_name NVARCHAR(200) N'$.warning_light_name',
    component_category NVARCHAR(120) N'$.component_category',
    severity NVARCHAR(120) N'$.severity',
    recommended_service NVARCHAR(200) N'$.recommended_service',
    recommended_service_type NVARCHAR(200) N'$.recommended_service_type',
    campaign_id NVARCHAR(100) N'$.campaign_id',
    recall_status NVARCHAR(120) N'$.recall_status',
    recall_relevance NVARCHAR(120) N'$.recall_relevance',
    url NVARCHAR(1000) N'$.url',
    source_url NVARCHAR(1000) N'$.source_url'
) AS citation_fields
OUTER APPLY (
    SELECT
        CASE
            WHEN CHARINDEX(N'recall:', COALESCE(citation_fields.content, N'')) > 0 THEN CHARINDEX(N'recall:', citation_fields.content)
            WHEN CHARINDEX(N'warning_light:', COALESCE(citation_fields.content, N'')) > 0 THEN CHARINDEX(N'warning_light:', citation_fields.content)
            WHEN CHARINDEX(N'maintenance_service:', COALESCE(citation_fields.content, N'')) > 0 THEN CHARINDEX(N'maintenance_service:', citation_fields.content)
            WHEN CHARINDEX(N'scenario:', COALESCE(citation_fields.content, N'')) > 0 THEN CHARINDEX(N'scenario:', citation_fields.content)
            WHEN CHARINDEX(N'image:', COALESCE(citation_fields.content, N'')) > 0 THEN CHARINDEX(N'image:', citation_fields.content)
        END AS document_id_position
) AS citation_position
OUTER APPLY (
    SELECT
        CASE
            WHEN citation_position.document_id_position IS NULL THEN NULL
            ELSE NULLIF(
                LTRIM(RTRIM(REPLACE(
                    SUBSTRING(
                        citation_fields.content,
                        citation_position.document_id_position,
                        CHARINDEX(CHAR(10), citation_fields.content + CHAR(10), citation_position.document_id_position) - citation_position.document_id_position
                    ),
                    CHAR(13),
                    N''
                ))),
                N''
            )
        END AS document_id,
        CASE
            WHEN citation_fields.content LIKE N'%NHTSA_RECALLS_API%' THEN N'NHTSA_RECALLS_API'
            WHEN citation_fields.content LIKE N'%STANDARD_64_WARNING_LIGHT_GUIDE_PLUS_OEM_REFERENCE%' THEN N'STANDARD_64_WARNING_LIGHT_GUIDE_PLUS_OEM_REFERENCE'
            WHEN citation_fields.content LIKE N'%TEAM_STRUCTURED_SERVICE_MAP_FROM_STANDARD_64_WARNING_CATALOG%' THEN N'TEAM_STRUCTURED_SERVICE_MAP_FROM_STANDARD_64_WARNING_CATALOG'
            WHEN citation_fields.content LIKE N'%STANDARD_64_WARNING_LIGHT_PLUS_NHTSA_RECALL%' THEN N'STANDARD_64_WARNING_LIGHT_PLUS_NHTSA_RECALL'
            WHEN citation_fields.content LIKE N'%WARNING_LIGHT_IMAGE_METADATA%' THEN N'WARNING_LIGHT_IMAGE_METADATA'
        END AS source_type
) AS citation_content;
GO

SELECT
    'query_log' AS object_name,
    COUNT(*) AS row_count
FROM dbo.query_log
UNION ALL
SELECT
    'vw_query_log',
    COUNT(*)
FROM dbo.vw_query_log;
GO
