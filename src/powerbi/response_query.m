let
    Config = LoadConfig(PowerBIProjectRoot),
    Source = Query(
        BasePrompt,
        Config[AzureLogicAppUrl],
        BaseTopK,
        BaseIncludeImageEvidence
    )
in
    Source