/*
WARNY-BI table DDL.

Run this script from a connection whose active database is warny_bi.
It is intentionally schema-only so it can be reused for local SQL Server and
Azure SQL. CSV loading belongs in 02_load_data.sql or the DBeaver import flow.
*/

USE warny_bi;
GO

SET NOCOUNT ON;
GO

IF OBJECT_ID(N'dbo.warning_light_image_catalog', N'U') IS NOT NULL
    DROP TABLE dbo.warning_light_image_catalog;
GO

IF OBJECT_ID(N'dbo.recall_data', N'U') IS NOT NULL
    DROP TABLE dbo.recall_data;
GO

IF OBJECT_ID(N'dbo.scenario_validation', N'U') IS NOT NULL
    DROP TABLE dbo.scenario_validation;
GO

IF OBJECT_ID(N'dbo.maintenance_service_map', N'U') IS NOT NULL
    DROP TABLE dbo.maintenance_service_map;
GO

IF OBJECT_ID(N'dbo.warning_light_catalog', N'U') IS NOT NULL
    DROP TABLE dbo.warning_light_catalog;
GO

IF OBJECT_ID(N'dbo.dataset_sources', N'U') IS NOT NULL
    DROP TABLE dbo.dataset_sources;
GO

CREATE TABLE dbo.dataset_sources (
    source_id NVARCHAR(50) NOT NULL,
    source_name NVARCHAR(255) NULL,
    source_type NVARCHAR(50) NULL,
    source_url NVARCHAR(255) NULL,
    used_for NVARCHAR(255) NULL,
    license_or_access_note NVARCHAR(255) NULL,
    collection_note NVARCHAR(255) NULL,
    CONSTRAINT pk_dataset_sources PRIMARY KEY (source_id)
);
GO

CREATE TABLE dbo.warning_light_catalog (
    warning_light_id NVARCHAR(50) NOT NULL,
    warning_light_name NVARCHAR(50) NULL,
    symbol_label NVARCHAR(50) NULL,
    color NVARCHAR(50) NULL,
    severity NVARCHAR(50) NULL,
    stop_immediately NVARCHAR(255) NULL,
    component_category NVARCHAR(50) NULL,
    description NVARCHAR(255) NULL,
    possible_causes NVARCHAR(255) NULL,
    immediate_action NVARCHAR(255) NULL,
    recommended_service_type NVARCHAR(50) NULL,
    rag_ready_content NVARCHAR(MAX) NULL,
    source_type NVARCHAR(50) NULL,
    source_url NVARCHAR(255) NULL,
    review_status NVARCHAR(255) NULL,
    CONSTRAINT pk_warning_light_catalog PRIMARY KEY (warning_light_id)
);
GO

CREATE TABLE dbo.maintenance_service_map (
    service_type_id NVARCHAR(50) NOT NULL,
    recommended_service_type NVARCHAR(50) NULL,
    component_category NVARCHAR(255) NULL,
    urgency_level NVARCHAR(50) NULL,
    typical_customer_message NVARCHAR(MAX) NULL,
    typical_action NVARCHAR(255) NULL,
    business_user NVARCHAR(255) NULL,
    expected_value NVARCHAR(255) NULL,
    evidence_level_required NVARCHAR(255) NULL,
    rag_ready_content NVARCHAR(MAX) NULL,
    source_type NVARCHAR(255) NULL,
    source_url NVARCHAR(255) NULL,
    review_status NVARCHAR(50) NULL,
    CONSTRAINT pk_maintenance_service_map PRIMARY KEY (service_type_id)
);
GO

CREATE TABLE dbo.recall_data (
    recall_record_id NVARCHAR(50) NOT NULL,
    campaign_id NVARCHAR(50) NULL,
    make NVARCHAR(50) NULL,
    model NVARCHAR(50) NULL,
    model_year INT NULL,
    component NVARCHAR(255) NULL,
    defect_summary NVARCHAR(MAX) NULL,
    consequence NVARCHAR(MAX) NULL,
    remedy NVARCHAR(MAX) NULL,
    related_warning_light_id NVARCHAR(50) NULL,
    recall_relevance_rule NVARCHAR(MAX) NULL,
    severity_override NVARCHAR(50) NULL,
    rag_ready_content NVARCHAR(MAX) NULL,
    source_type NVARCHAR(50) NULL,
    source_url NVARCHAR(255) NULL,
    review_status NVARCHAR(255) NULL,
    CONSTRAINT pk_recall_data PRIMARY KEY (recall_record_id),
    CONSTRAINT fk_recall_data_warning_light_catalog
        FOREIGN KEY (related_warning_light_id)
        REFERENCES dbo.warning_light_catalog (warning_light_id)
);
GO

CREATE TABLE dbo.scenario_validation (
    scenario_id NVARCHAR(50) NOT NULL,
    make NVARCHAR(50) NULL,
    model NVARCHAR(50) NULL,
    model_year INT NULL,
    warning_light_name NVARCHAR(50) NULL,
    warning_light_color NVARCHAR(50) NULL,
    user_symptom NVARCHAR(255) NULL,
    expected_severity NVARCHAR(50) NULL,
    expected_action NVARCHAR(255) NULL,
    expected_recall_relevance NVARCHAR(255) NULL,
    expected_service_type NVARCHAR(50) NULL,
    expected_output_format NVARCHAR(255) NULL,
    pass_condition NVARCHAR(255) NULL,
    failure_mode_to_watch NVARCHAR(255) NULL,
    source_type NVARCHAR(50) NULL,
    source_url NVARCHAR(255) NULL,
    review_status NVARCHAR(50) NULL,
    CONSTRAINT pk_scenario_validation PRIMARY KEY (scenario_id)
);
GO

CREATE TABLE dbo.warning_light_image_catalog (
    image_id NVARCHAR(50) NOT NULL,
    class_folder NVARCHAR(50) NULL,
    class_id_raw NVARCHAR(50) NULL,
    image_file NVARCHAR(255) NULL,
    file_ext NVARCHAR(50) NULL,
    image_count_in_class INT NULL,
    warning_light_id NVARCHAR(50) NULL,
    label NVARCHAR(50) NULL,
    label_confidence NVARCHAR(50) NULL,
    mapping_status NVARCHAR(50) NULL,
    image_url_or_blob_path NVARCHAR(255) NULL,
    note NVARCHAR(255) NULL,
    source_type NVARCHAR(50) NULL,
    source_url NVARCHAR(255) NULL,
    CONSTRAINT pk_warning_light_image_catalog PRIMARY KEY (image_id),
    CONSTRAINT fk_warning_light_image_catalog_warning_light_catalog
        FOREIGN KEY (warning_light_id)
        REFERENCES dbo.warning_light_catalog (warning_light_id)
);
GO

CREATE INDEX ix_warning_light_catalog_service_type
    ON dbo.warning_light_catalog (recommended_service_type);
GO

CREATE INDEX ix_warning_light_catalog_component
    ON dbo.warning_light_catalog (component_category);
GO

CREATE INDEX ix_recall_data_vehicle
    ON dbo.recall_data (make, model, model_year);
GO

CREATE INDEX ix_recall_data_warning_light
    ON dbo.recall_data (related_warning_light_id);
GO

CREATE INDEX ix_warning_light_image_catalog_warning_light
    ON dbo.warning_light_image_catalog (warning_light_id);
GO
