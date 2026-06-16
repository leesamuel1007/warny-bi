let
    Config = LoadConfig(PowerBIProjectRoot),
    Source = Query(
        BasePrompt,
        Config[RagApiUrl],
        BaseTopK,
        BaseIncludeImageEvidence
    )
in
    Source
