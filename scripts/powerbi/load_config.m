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
            ActiveBackend =
                if Record.HasFields(Source, "ActiveBackend") then
                    Text.Trim(Text.From(Source[ActiveBackend]))
                else
                    "",
            Backends =
                if Record.HasFields(Source, "Backends") and Source[Backends] is record then
                    Source[Backends]
                else
                    [],
            SelectedBackend =
                if ActiveBackend <> "" and Record.HasFields(Backends, ActiveBackend) then
                    Record.Field(Backends, ActiveBackend)
                else
                    [],
            SelectedConfig =
                if SelectedBackend is record then
                    Record.AddField(SelectedBackend, "ActiveBackend", ActiveBackend)
                else
                    [],
            RequiredFields =
                if ActiveBackend = "AzureDirect" then
                    {
                        "AzureOpenAIEndpointUrl",
                        "AzureOpenAIKey",
                        "GPT4oDeploymentName",
                        "AzureAISearchEndpoint",
                        "AzureAISearchIndexName",
                        "AzureAISearchAdminKey",
                        "SqlServer",
                        "SqlDatabase"
                    }
                else
                    {"RagApiUrl", "SqlServer", "SqlDatabase"},
            MissingFields = List.Select(
                RequiredFields,
                each not Record.HasFields(SelectedConfig, _)
                    or Record.Field(SelectedConfig, _) = null
                    or Text.Trim(Text.From(Record.Field(SelectedConfig, _))) = ""
            )
        in
            if CleanRoot = "" then
                error Error.Record(
                    "Missing Power BI project root",
                    "Set PowerBIProjectRoot to the local WARNY-BI repository path.",
                    "PowerBIProjectRoot"
                )
            else if ActiveBackend = "" then
                error Error.Record(
                    "Missing active Power BI backend",
                    "config/powerbi.secrets.json must set ActiveBackend.",
                    "ActiveBackend"
                )
            else if not Record.HasFields(Backends, ActiveBackend) then
                error Error.Record(
                    "Unknown Power BI backend",
                    "ActiveBackend must match a key under Backends.",
                    ActiveBackend
                )
            else if List.Count(MissingFields) > 0 then
                error Error.Record(
                    "Missing local Power BI configuration",
                    "The selected backend in config/powerbi.secrets.json is missing required fields.",
                    Text.Combine(MissingFields, ", ")
                )
            else
                SelectedConfig
in
    LoadConfig
