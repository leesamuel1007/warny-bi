/*
WARNY-BI query interaction log.

Run this script in the same Azure SQL database used by Power BI. It creates
empty tables for logged prompt/response rows and views for the Page 3 dashboard.

This script is safe to rerun. It creates missing tables/indexes and refreshes
the views without dropping existing log rows.
*/

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.query_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.query_log (
        query_id UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT DF_query_log_query_id DEFAULT NEWID(),
        created_at_utc DATETIME2(3) NOT NULL
            CONSTRAINT DF_query_log_created_at_utc DEFAULT SYSUTCDATETIME(),
        pipeline NVARCHAR(30) NOT NULL,
        user_prompt NVARCHAR(MAX) NOT NULL,

        answer_summary NVARCHAR(MAX) NULL,
        parsed_make NVARCHAR(100) NULL,
        parsed_model NVARCHAR(100) NULL,
        parsed_model_year INT NULL,
        parsed_warning_light NVARCHAR(200) NULL,
        warning_light_id NVARCHAR(50) NULL,
        component_category NVARCHAR(120) NULL,

        severity NVARCHAR(120) NULL,
        severity_level INT NULL,
        stop_immediately BIT NULL,
        recommended_service NVARCHAR(200) NULL,

        recall_status NVARCHAR(200) NULL,
        recall_status_level INT NULL,
        primary_campaign NVARCHAR(100) NULL,
        recall_interpretation NVARCHAR(MAX) NULL,

        evidence_count INT NOT NULL
            CONSTRAINT DF_query_log_evidence_count DEFAULT 0,
        recall_candidate_count INT NOT NULL
            CONSTRAINT DF_query_log_recall_candidate_count DEFAULT 0,
        warning_guide_count INT NOT NULL
            CONSTRAINT DF_query_log_warning_guide_count DEFAULT 0,
        service_map_count INT NOT NULL
            CONSTRAINT DF_query_log_service_map_count DEFAULT 0,
        validation_scenario_count INT NOT NULL
            CONSTRAINT DF_query_log_validation_scenario_count DEFAULT 0,
        image_support_count INT NOT NULL
            CONSTRAINT DF_query_log_image_support_count DEFAULT 0,

        top_document_id NVARCHAR(160) NULL,
        top_source_type NVARCHAR(255) NULL,
        top_confidence_label NVARCHAR(50) NULL,
        top_rank_score FLOAT NULL,
        top_score FLOAT NULL,

        CONSTRAINT PK_query_log PRIMARY KEY CLUSTERED (query_id)
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_query_log_created_at_utc'
      AND object_id = OBJECT_ID(N'dbo.query_log')
)
BEGIN
    CREATE INDEX IX_query_log_created_at_utc
    ON dbo.query_log (created_at_utc DESC);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_query_log_pipeline_created_at_utc'
      AND object_id = OBJECT_ID(N'dbo.query_log')
)
BEGIN
    CREATE INDEX IX_query_log_pipeline_created_at_utc
    ON dbo.query_log (pipeline, created_at_utc DESC);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_query_log_warning_light'
      AND object_id = OBJECT_ID(N'dbo.query_log')
)
BEGIN
    CREATE INDEX IX_query_log_warning_light
    ON dbo.query_log (parsed_warning_light, warning_light_id);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_query_log_vehicle'
      AND object_id = OBJECT_ID(N'dbo.query_log')
)
BEGIN
    CREATE INDEX IX_query_log_vehicle
    ON dbo.query_log (parsed_make, parsed_model, parsed_model_year);
END;
GO

IF OBJECT_ID(N'dbo.query_log_evidence', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.query_log_evidence (
        query_id UNIQUEIDENTIFIER NOT NULL,
        evidence_rank INT NOT NULL,
        document_id NVARCHAR(160) NULL,
        source_type NVARCHAR(255) NULL,
        source_type_label NVARCHAR(255) NULL,
        source_id NVARCHAR(160) NULL,
        confidence_label NVARCHAR(50) NULL,
        evidence_level NVARCHAR(100) NULL,
        evidence_level_label NVARCHAR(120) NULL,
        warning_light_id NVARCHAR(50) NULL,
        warning_light_name NVARCHAR(200) NULL,
        make NVARCHAR(100) NULL,
        model NVARCHAR(100) NULL,
        model_year INT NULL,
        campaign_id NVARCHAR(100) NULL,
        recall_relevance NVARCHAR(120) NULL,
        recall_relevance_label NVARCHAR(160) NULL,
        component_category NVARCHAR(120) NULL,
        severity NVARCHAR(120) NULL,
        severity_label NVARCHAR(120) NULL,
        recommended_service_type NVARCHAR(200) NULL,
        recommended_service_label NVARCHAR(200) NULL,
        source_url NVARCHAR(1000) NULL,
        content_preview NVARCHAR(1000) NULL,
        rank_score FLOAT NULL,
        score FLOAT NULL,

        CONSTRAINT PK_query_log_evidence PRIMARY KEY CLUSTERED (query_id, evidence_rank),
        CONSTRAINT FK_query_log_evidence_query_log
            FOREIGN KEY (query_id)
            REFERENCES dbo.query_log (query_id)
            ON DELETE CASCADE
    );
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_query_log_evidence_document'
      AND object_id = OBJECT_ID(N'dbo.query_log_evidence')
)
BEGIN
    CREATE INDEX IX_query_log_evidence_document
    ON dbo.query_log_evidence (document_id);
END;
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.indexes
    WHERE name = N'IX_query_log_evidence_level'
      AND object_id = OBJECT_ID(N'dbo.query_log_evidence')
)
BEGIN
    CREATE INDEX IX_query_log_evidence_level
    ON dbo.query_log_evidence (evidence_level, evidence_level_label);
END;
GO

CREATE OR ALTER VIEW dbo.vw_query_log_dashboard
AS
SELECT
    query_id,
    created_at_utc,
    CAST(created_at_utc AS DATE) AS created_date_utc,
    pipeline,
    user_prompt,
    answer_summary,
    parsed_make,
    parsed_model,
    parsed_model_year,
    parsed_warning_light,
    warning_light_id,
    component_category,
    severity,
    severity_level,
    stop_immediately,
    recommended_service,
    recall_status,
    recall_status_level,
    primary_campaign,
    recall_interpretation,
    evidence_count,
    recall_candidate_count,
    warning_guide_count,
    service_map_count,
    validation_scenario_count,
    image_support_count,
    top_document_id,
    top_source_type,
    top_confidence_label,
    top_rank_score,
    top_score,
    CASE
        WHEN severity_level >= 4 THEN N'Immediate stop'
        WHEN severity_level = 3 THEN N'Urgent'
        WHEN severity_level = 2 THEN N'Service soon'
        ELSE N'Informational or unknown'
    END AS severity_bucket,
    CASE
        WHEN recall_status_level >= 3 THEN N'Recall candidate'
        WHEN recall_status_level = 2 THEN N'Recall review needed'
        WHEN recall_status_level = 1 THEN N'No retrieved recall candidate'
        ELSE N'Unknown'
    END AS recall_bucket,
    CASE
        WHEN stop_immediately = 1 OR severity_level >= 4 OR recall_status_level >= 3 THEN 1
        ELSE 0
    END AS high_impact_flag
FROM dbo.query_log;
GO

CREATE OR ALTER VIEW dbo.vw_query_log_evidence
AS
SELECT
    q.pipeline,
    q.created_at_utc,
    q.user_prompt,
    q.parsed_make,
    q.parsed_model,
    q.parsed_model_year,
    q.parsed_warning_light,
    e.*
FROM dbo.query_log_evidence AS e
INNER JOIN dbo.query_log AS q
    ON e.query_id = q.query_id;
GO

SELECT
    'query_log' AS object_name,
    COUNT(*) AS row_count
FROM dbo.query_log
UNION ALL
SELECT
    'query_log_evidence',
    COUNT(*)
FROM dbo.query_log_evidence
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
