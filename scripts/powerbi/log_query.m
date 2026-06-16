let
    Config = LoadConfig(PowerBIProjectRoot),
    Source = Sql.Database(Config[SqlServer], Config[SqlDatabase]),
    Result = Source{[Schema = "dbo", Item = "vw_query_log"]}[Data]
in
    Result
