let
    NormalizeEndpoint = (endpoint as text) as text =>
        let
            Trimmed = Text.Trim(endpoint),
            Normalized = if Text.End(Trimmed, 1) = "/" then Text.Start(Trimmed, Text.Length(Trimmed) - 1) else Trimmed
        in
            Normalized,

    FirstNonNull = (values as list, optional fallback as any) as any =>
        let
            NonNullValues = List.RemoveNulls(values),
            Result = if List.Count(NonNullValues) = 0 then fallback else NonNullValues{0}
        in
            Result,

    NormalizeCitation = (citation as record, index as number) as record =>
        let
            Content = try Text.From(citation[content]) otherwise "",
            Url = try Text.From(citation[url]) otherwise null,
            Title = try Text.From(citation[title]) otherwise null,
            Filepath = try Text.From(citation[filepath]) otherwise null,
            ChunkId = try Text.From(citation[chunk_id]) otherwise null,
            DocumentId = FirstNonNull({ChunkId, Filepath, Title}, "azure-citation-" & Text.From(index))
        in
            [
                score = null,
                document_id = DocumentId,
                source_type = "AZURE_AI_SEARCH",
                source_id = ChunkId,
                warning_light_id = null,
                warning_light_name = null,
                make = null,
                model = null,
                model_year = null,
                component_category = null,
                severity = null,
                recommended_service_type = null,
                source_url = Url,
                image_path = null,
                review_status = null,
                content_preview = Text.Start(Content, 240),
                rank_score = null,
                match_reasons = {}
            ],

    NormalizeCitations = (citations as list) as list =>
        List.Transform(
            List.Positions(citations),
            each NormalizeCitation(citations{_}, _ + 1)
        ),

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
                    // Keep this aligned with config/prompts/rag_answer.txt.
                    [
                        role = "system",
                        content = "You are WARNY-BI, a vehicle warning-light triage assistant for a Power BI business-intelligence dashboard. Use only retrieved evidence. Do not claim a confirmed diagnosis. Separate generic warning-light guidance from recall applicability. Say when VIN lookup, OEM manual review, or professional service inspection is required. Write plain text for a Power BI text visual and keep each section short and operational. Rewrite internal codes, enum values, and machine labels into human-readable dashboard text; do not output raw labels such as SEARCH_..., URGENT_OR_IMMEDIATE_STOP, SERVICE_SOON_TO_URGENT, AIRBAG_SRS_DIAGNOSTIC, source_type values, or review_status values unless they are document IDs in Evidence used. Treat image/icon metadata as visual support only unless the user asks about an image, symbol, icon, photo, or screenshot."
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
            Citations = if Context = null then {} else try Context[citations] otherwise {},
            Evidence = NormalizeCitations(Citations)
        in
            [
                query = query,
                parsed_intent = null,
                answer = Message[content],
                evidence = Evidence,
                citations = Citations,
                raw = Response
            ]
in
    AzureRagQuery
