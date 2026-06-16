/*
WARNY-BI RAG retrieval view.

Run this after 01_create_tables.sql and data load/import are complete.
The resulting view is the shared retrieval surface for Azure AI Search,
Qdrant ingestion, and Power BI evidence inspection.
*/

-- Remove the following two lines if running in Azure DB.
USE warny_bi;
GO

CREATE OR ALTER VIEW dbo.vw_rag_documents
AS
SELECT
    REPLACE(CONCAT(N'warning_light:', warning_light_id), N':', N'-') AS search_key,
    CONCAT(N'warning_light:', warning_light_id) AS document_id,
    COALESCE(NULLIF(source_type, N''), N'WARNING_LIGHT') AS source_type,
    warning_light_id AS source_id,
    warning_light_id,
    warning_light_name,
    CAST(NULL AS NVARCHAR(50)) AS make,
    CAST(NULL AS NVARCHAR(50)) AS model,
    CAST(NULL AS INT) AS model_year,
    component_category,
    severity,
    recommended_service_type,
    COALESCE(
        NULLIF(rag_ready_content, N''),
        CONCAT(
            N'Warning light ', warning_light_id, N': ', warning_light_name,
            N'. Symbol label: ', COALESCE(symbol_label, N''),
            N'. Color: ', COALESCE(color, N''),
            N'. Severity: ', COALESCE(severity, N''),
            N'. Component category: ', COALESCE(component_category, N''),
            N'. Meaning: ', COALESCE(description, N''),
            N'. Possible causes: ', COALESCE(possible_causes, N''),
            N'. Immediate action: ', COALESCE(immediate_action, N''),
            N'. Recommended service type: ', COALESCE(recommended_service_type, N'')
        )
    ) AS content,
    source_url,
    CAST(NULL AS NVARCHAR(255)) AS image_path,
    review_status
FROM dbo.warning_light_catalog

UNION ALL

SELECT
    REPLACE(CONCAT(N'recall:', r.recall_record_id), N':', N'-') AS search_key,
    CONCAT(N'recall:', r.recall_record_id) AS document_id,
    COALESCE(NULLIF(r.source_type, N''), N'RECALL') AS source_type,
    r.recall_record_id AS source_id,
    r.related_warning_light_id AS warning_light_id,
    w.warning_light_name,
    r.make,
    r.model,
    r.model_year,
    COALESCE(w.component_category, r.component) AS component_category,
    COALESCE(r.severity_override, w.severity) AS severity,
    w.recommended_service_type,
    COALESCE(
        NULLIF(r.rag_ready_content, N''),
        CONCAT(
            N'Recall record ', r.recall_record_id,
            N'. Campaign ', COALESCE(r.campaign_id, N''),
            N'. Vehicle: ', COALESCE(r.make, N''), N' ', COALESCE(r.model, N''), N' ', COALESCE(CONVERT(NVARCHAR(20), r.model_year), N''),
            N'. Component: ', COALESCE(r.component, N''),
            N'. Defect summary: ', COALESCE(r.defect_summary, N''),
            N'. Consequence: ', COALESCE(r.consequence, N''),
            N'. Remedy: ', COALESCE(r.remedy, N''),
            N'. Related warning light: ', COALESCE(r.related_warning_light_id, N''), N' ', COALESCE(w.warning_light_name, N'')
        )
    ) AS content,
    r.source_url,
    CAST(NULL AS NVARCHAR(255)) AS image_path,
    r.review_status
FROM dbo.recall_data AS r
LEFT JOIN dbo.warning_light_catalog AS w
    ON r.related_warning_light_id = w.warning_light_id

UNION ALL

SELECT
    REPLACE(CONCAT(N'maintenance_service:', service_type_id), N':', N'-') AS search_key,
    CONCAT(N'maintenance_service:', service_type_id) AS document_id,
    COALESCE(NULLIF(source_type, N''), N'MAINTENANCE_SERVICE') AS source_type,
    service_type_id AS source_id,
    CAST(NULL AS NVARCHAR(50)) AS warning_light_id,
    CAST(NULL AS NVARCHAR(50)) AS warning_light_name,
    CAST(NULL AS NVARCHAR(50)) AS make,
    CAST(NULL AS NVARCHAR(50)) AS model,
    CAST(NULL AS INT) AS model_year,
    component_category,
    urgency_level AS severity,
    recommended_service_type,
    COALESCE(
        NULLIF(rag_ready_content, N''),
        CONCAT(
            N'Maintenance service map: ', recommended_service_type,
            N'. Categories: ', COALESCE(component_category, N''),
            N'. Urgency: ', COALESCE(urgency_level, N''),
            N'. Typical customer message: ', COALESCE(typical_customer_message, N''),
            N'. Typical action: ', COALESCE(typical_action, N'')
        )
    ) AS content,
    source_url,
    CAST(NULL AS NVARCHAR(255)) AS image_path,
    review_status
FROM dbo.maintenance_service_map

UNION ALL

SELECT
    REPLACE(CONCAT(N'image:', i.image_id), N':', N'-') AS search_key,
    CONCAT(N'image:', i.image_id) AS document_id,
    COALESCE(NULLIF(i.source_type, N''), N'IMAGE_METADATA') AS source_type,
    i.image_id AS source_id,
    i.warning_light_id,
    COALESCE(w.warning_light_name, i.label) AS warning_light_name,
    CAST(NULL AS NVARCHAR(50)) AS make,
    CAST(NULL AS NVARCHAR(50)) AS model,
    CAST(NULL AS INT) AS model_year,
    w.component_category,
    w.severity,
    w.recommended_service_type,
    CONCAT(
        N'Warning-light image metadata ', i.image_id,
        N'. Warning light: ', COALESCE(i.warning_light_id, N''), N' ', COALESCE(w.warning_light_name, i.label, N''),
        N'. Class folder: ', COALESCE(i.class_folder, N''),
        N'. Label confidence: ', COALESCE(i.label_confidence, N''),
        N'. Mapping status: ', COALESCE(i.mapping_status, N''),
        N'. Note: ', COALESCE(i.note, N'')
    ) AS content,
    i.source_url,
    COALESCE(NULLIF(i.image_url_or_blob_path, N''), i.image_file) AS image_path,
    COALESCE(i.mapping_status, w.review_status) AS review_status
FROM dbo.warning_light_image_catalog AS i
LEFT JOIN dbo.warning_light_catalog AS w
    ON i.warning_light_id = w.warning_light_id

UNION ALL

SELECT
    REPLACE(CONCAT(N'scenario:', scenario_id), N':', N'-') AS search_key,
    CONCAT(N'scenario:', scenario_id) AS document_id,
    COALESCE(NULLIF(source_type, N''), N'VALIDATION_SCENARIO') AS source_type,
    scenario_id AS source_id,
    CAST(NULL AS NVARCHAR(50)) AS warning_light_id,
    warning_light_name,
    make,
    model,
    model_year,
    CAST(NULL AS NVARCHAR(255)) AS component_category,
    expected_severity AS severity,
    expected_service_type AS recommended_service_type,
    CONCAT(
        N'Validation scenario ', scenario_id,
        N'. Vehicle: ', COALESCE(make, N''), N' ', COALESCE(model, N''), N' ', COALESCE(CONVERT(NVARCHAR(20), model_year), N''),
        N'. Warning light: ', COALESCE(warning_light_name, N''),
        N'. Warning light color: ', COALESCE(warning_light_color, N''),
        N'. User symptom: ', COALESCE(user_symptom, N''),
        N'. Expected severity: ', COALESCE(expected_severity, N''),
        N'. Expected action: ', COALESCE(expected_action, N''),
        N'. Expected recall relevance: ', COALESCE(expected_recall_relevance, N''),
        N'. Expected service type: ', COALESCE(expected_service_type, N''),
        N'. Pass condition: ', COALESCE(pass_condition, N''),
        N'. Failure mode to watch: ', COALESCE(failure_mode_to_watch, N'')
    ) AS content,
    source_url,
    CAST(NULL AS NVARCHAR(255)) AS image_path,
    review_status
FROM dbo.scenario_validation;
GO
