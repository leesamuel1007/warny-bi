let
    Config = LoadConfig(PowerBIProjectRoot),
    Source = Sql.Database(Config[AzureSqlServer], Config[AzureSqlDatabase]),
    Result = Source{[Schema = "dbo", Item = "vw_query_log"]}[Data]
in
    Result
