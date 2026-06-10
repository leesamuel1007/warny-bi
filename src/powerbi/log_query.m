let
    LogQuery = (
        sqlServer as text,
        database as text,
        optional viewName as nullable text,
        optional schemaName as nullable text
    ) as table =>
        let
            Schema = if schemaName = null or Text.Trim(schemaName) = "" then "dbo" else Text.Trim(schemaName),
            View = if viewName = null or Text.Trim(viewName) = "" then "vw_query_log_dashboard" else Text.Trim(viewName),
            Source = Sql.Database(sqlServer, database),
            Result = Source{[Schema = Schema, Item = View]}[Data]
        in
            Result
in
    LogQuery
