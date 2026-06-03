/*
WARNY-BI SQL load verification.

Run this after creating tables and importing data/processed/{name}.csv into warny_bi.
*/

USE warny_bi;
GO

SET NOCOUNT ON;
GO

SELECT
    'dataset_sources' AS table_name,
    COUNT(*) AS actual_rows,
    7 AS expected_rows
FROM dbo.dataset_sources
UNION ALL
SELECT
    'maintenance_service_map',
    COUNT(*),
    34
FROM dbo.maintenance_service_map
UNION ALL
SELECT
    'recall_data',
    COUNT(*),
    165
FROM dbo.recall_data
UNION ALL
SELECT
    'scenario_validation',
    COUNT(*),
    20
FROM dbo.scenario_validation
UNION ALL
SELECT
    'warning_light_catalog',
    COUNT(*),
    64
FROM dbo.warning_light_catalog
UNION ALL
SELECT
    'warning_light_image_catalog',
    COUNT(*),
    302
FROM dbo.warning_light_image_catalog;
GO

SELECT
    'recall_data.related_warning_light_id' AS check_name,
    COUNT(*) AS orphan_count
FROM dbo.recall_data AS r
LEFT JOIN dbo.warning_light_catalog AS w
    ON r.related_warning_light_id = w.warning_light_id
WHERE r.related_warning_light_id IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(r.related_warning_light_id)), N'') IS NOT NULL
  AND w.warning_light_id IS NULL;
GO

SELECT
    'warning_light_image_catalog.warning_light_id' AS check_name,
    COUNT(*) AS orphan_count
FROM dbo.warning_light_image_catalog AS i
LEFT JOIN dbo.warning_light_catalog AS w
    ON i.warning_light_id = w.warning_light_id
WHERE i.warning_light_id IS NOT NULL
  AND NULLIF(LTRIM(RTRIM(i.warning_light_id)), N'') IS NOT NULL
  AND w.warning_light_id IS NULL;
GO

SELECT
    'warning_light_catalog.rag_ready_content' AS check_name,
    COUNT(*) AS blank_rag_ready_content_count
FROM dbo.warning_light_catalog
WHERE NULLIF(LTRIM(RTRIM(rag_ready_content)), N'') IS NULL
UNION ALL
SELECT
    'maintenance_service_map.rag_ready_content',
    COUNT(*)
FROM dbo.maintenance_service_map
WHERE NULLIF(LTRIM(RTRIM(rag_ready_content)), N'') IS NULL
UNION ALL
SELECT
    'recall_data.rag_ready_content',
    COUNT(*)
FROM dbo.recall_data
WHERE NULLIF(LTRIM(RTRIM(rag_ready_content)), N'') IS NULL;
GO

SELECT TOP 10
    warning_light_id,
    warning_light_name,
    color,
    severity,
    recommended_service_type,
    component_category
FROM dbo.warning_light_catalog
ORDER BY warning_light_id;
GO

SELECT TOP 10
    r.recall_record_id,
    r.make,
    r.model,
    r.model_year,
    r.component,
    r.related_warning_light_id,
    w.warning_light_name
FROM dbo.recall_data AS r
LEFT JOIN dbo.warning_light_catalog AS w
    ON r.related_warning_light_id = w.warning_light_id
ORDER BY r.recall_record_id;
GO

IF OBJECT_ID(N'dbo.vw_rag_documents', N'V') IS NOT NULL
BEGIN
    SELECT
        'vw_rag_documents' AS view_name,
        COUNT(*) AS actual_rows,
        585 AS expected_rows
    FROM dbo.vw_rag_documents;

    SELECT
        source_type,
        COUNT(*) AS document_count
    FROM dbo.vw_rag_documents
    GROUP BY source_type
    ORDER BY source_type;

    SELECT
        document_id,
        COUNT(*) AS duplicate_count
    FROM dbo.vw_rag_documents
    GROUP BY document_id
    HAVING COUNT(*) > 1
    ORDER BY duplicate_count DESC, document_id;

    SELECT
        COUNT(*) AS blank_content_count
    FROM dbo.vw_rag_documents
    WHERE NULLIF(LTRIM(RTRIM(content)), N'') IS NULL;

    SELECT TOP 20
        document_id,
        source_type,
        source_id,
        warning_light_id,
        warning_light_name,
        make,
        model,
        model_year,
        severity,
        recommended_service_type,
        LEFT(content, 200) AS content_preview
    FROM dbo.vw_rag_documents
    ORDER BY document_id;
END;
GO
