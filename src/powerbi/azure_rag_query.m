let
    NormalizeEndpoint = (endpoint as text) as text =>
        let
            Trimmed = Text.Trim(endpoint),
            Normalized = if Text.End(Trimmed, 1) = "/" then Text.Start(Trimmed, Text.Length(Trimmed) - 1) else Trimmed
        in
            Normalized,

    BuildSearchParameters = (
        searchEndpoint as text,
        searchKey as text,
        searchIndex as text,
        optional embeddingDeployment as nullable text,
        optional queryType as nullable text,
        optional semanticConfiguration as nullable text,
        optional topK as nullable number,
        optional strictness as nullable number,
        optional filter as nullable text
    ) as record =>
        let
            BaseParameters = [
                endpoint = NormalizeEndpoint(searchEndpoint),
                index_name = searchIndex,
                authentication = [
                    type = "api_key",
                    key = searchKey
                ],
                top_n_documents = if topK = null then 5 else Int64.From(topK),
                strictness = if strictness = null then 3 else Int64.From(strictness),
                query_type = if queryType = null then "simple" else queryType
            ],
            WithEmbedding =
                if embeddingDeployment = null then
                    BaseParameters
                else
                    Record.Combine({
                        BaseParameters,
                        [
                            embedding_dependency = [
                                type = "deployment_name",
                                deployment_name = embeddingDeployment
                            ]
                        ]
                    }),
            WithSemantic =
                if semanticConfiguration = null then
                    WithEmbedding
                else
                    Record.Combine({
                        WithEmbedding,
                        [semantic_configuration = semanticConfiguration]
                    }),
            WithFilter =
                if filter = null then
                    WithSemantic
                else
                    Record.Combine({
                        WithSemantic,
                        [filter = filter]
                    })
        in
            WithFilter,

    AzureRagQuery = (
        query as text,
        azureOpenAIEndpoint as text,
        azureOpenAIKey as text,
        chatDeployment as text,
        searchEndpoint as text,
        searchKey as text,
        searchIndex as text,
        optional embeddingDeployment as nullable text,
        optional apiVersion as nullable text,
        optional queryType as nullable text,
        optional semanticConfiguration as nullable text,
        optional topK as nullable number,
        optional strictness as nullable number,
        optional filter as nullable text
    ) as record =>
        let
            Version = if apiVersion = null then "2024-05-01-preview" else apiVersion,
            Endpoint = NormalizeEndpoint(azureOpenAIEndpoint),
            SearchParameters = BuildSearchParameters(
                searchEndpoint,
                searchKey,
                searchIndex,
                embeddingDeployment,
                queryType,
                semanticConfiguration,
                topK,
                strictness,
                filter
            ),
            RequestBody = [
                messages = {
                    [
                        role = "system",
                        content = "You are WARNY-BI, a vehicle warning-light triage assistant for business intelligence. Use only retrieved evidence. Do not claim a confirmed diagnosis. Separate warning-light guidance from recall applicability and say when VIN, OEM manual, or service inspection confirmation is needed."
                    ],
                    [
                        role = "user",
                        content = query
                    ]
                },
                temperature = 0,
                data_sources = {
                    [
                        type = "azure_search",
                        parameters = SearchParameters
                    ]
                }
            ],
            Response = Json.Document(
                Web.Contents(
                    Endpoint,
                    [
                        RelativePath = "openai/deployments/" & chatDeployment & "/chat/completions",
                        Query = [#"api-version" = Version],
                        Headers = [
                            #"Content-Type" = "application/json",
                            #"api-key" = azureOpenAIKey
                        ],
                        Content = Json.FromValue(RequestBody)
                    ]
                )
            ),
            FirstChoice = Response[choices]{0},
            Message = FirstChoice[message],
            Context = try Message[context] otherwise null,
            Citations = if Context = null then {} else try Context[citations] otherwise {}
        in
            [
                query = query,
                answer = Message[content],
                citations = Citations,
                raw = Response
            ]
in
    AzureRagQuery
