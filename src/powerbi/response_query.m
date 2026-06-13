let
    Config = LoadConfig(PowerBIProjectRoot),
    Source = Query(
        BasePrompt,
        Config[AzureLogicAppUrl],
        5,
        false
    )
in
    Source
