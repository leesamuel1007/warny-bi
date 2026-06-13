let
    LoadConfig = (
        projectRoot as text,
        optional relativeSecretsPath as nullable text
    ) as record =>
        let
            CleanRoot = Text.Trim(projectRoot),
            RelativePath =
                if relativeSecretsPath = null or Text.Trim(relativeSecretsPath) = "" then
                    "config/powerbi.secrets.json"
                else
                    Text.Trim(relativeSecretsPath),
            Slash = "/",
            Backslash = Character.FromNumber(92),
            Root =
                if Text.End(CleanRoot, 1) = Slash or Text.End(CleanRoot, 1) = Backslash then
                    Text.Start(CleanRoot, Text.Length(CleanRoot) - 1)
                else
                    CleanRoot,
            Relative =
                if Text.Start(RelativePath, 1) = Slash or Text.Start(RelativePath, 1) = Backslash then
                    Text.Range(RelativePath, 1)
                else
                    RelativePath,
            ConfigPath = Root & Slash & Relative,
            Source = Json.Document(File.Contents(ConfigPath)),
            RequiredFields = {"AzureLogicAppUrl", "AzureSqlServer", "AzureSqlDatabase"},
            MissingFields = List.Select(
                RequiredFields,
                each not Record.HasFields(Source, _)
                    or Record.Field(Source, _) = null
                    or Text.Trim(Text.From(Record.Field(Source, _))) = ""
            )
        in
            if CleanRoot = "" then
                error Error.Record(
                    "Missing Power BI project root",
                    "Set PowerBIProjectRoot to the local WARNY-BI repository path.",
                    "PowerBIProjectRoot"
                )
            else if List.Count(MissingFields) > 0 then
                error Error.Record(
                    "Missing local Power BI configuration",
                    "config/powerbi.secrets.json is missing required fields.",
                    Text.Combine(MissingFields, ", ")
                )
            else
                Source
in
    LoadConfig
