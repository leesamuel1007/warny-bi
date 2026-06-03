SELECT
      DB_NAME() AS current_database,
      OBJECT_ID(N'dbo.dataset_sources', N'U') AS dataset_sources_table_id,
      OBJECT_ID(N'dbo.dataset_sources') AS dataset_sources_object_id;
  GO

  SELECT
      s.name AS schema_name,
      o.name AS object_name,
      o.type,
      o.type_desc,
      o.create_date
  FROM sys.objects AS o
  JOIN sys.schemas AS s
      ON o.schema_id = s.schema_id
  WHERE o.name LIKE N'%dataset%';
  GO

  SELECT
      name,
      type,
      type_desc,
      create_date
  FROM sys.objects
  WHERE name LIKE N'%dataset%'
     OR name LIKE N'%source%';
  GO

  
USE warny_bi;
GO

SELECT 'warning_light_catalog' AS table_name, COUNT(*) AS rows FROM dbo.warning_light_catalog
UNION ALL SELECT 'recall_data', COUNT(*) FROM dbo.recall_data
UNION ALL SELECT 'maintenance_service_map', COUNT(*) FROM dbo.maintenance_service_map
UNION ALL SELECT 'warning_light_image_catalog', COUNT(*) FROM dbo.warning_light_image_catalog
UNION ALL SELECT 'scenario_validation', COUNT(*) FROM dbo.scenario_validation;
GO
