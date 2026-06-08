let
    DefaultRoleInformation =
        "You are WARNY-BI, a vehicle warning-light triage assistant for a Power BI dashboard. Use only retrieved evidence. Do not claim a confirmed diagnosis. Separate warning-light guidance from recall applicability. Say when VIN lookup, OEM manual review, or professional service inspection is required. Return exactly one JSON object. Do not include Markdown, code fences, comments, or extra text. Always include these keys: summary, severity_label, severity_level, severity_color, severity_icon_key, stop_immediately, recommended_service, recall_status, recall_status_level, recall_status_color, recall_icon_key, possible_causes, immediate_action, primary_campaign, recall_interpretation, evidence_used, parsed. Do not rename keys, add alternate keys, or wrap the object in another object. The parsed object must include make, model, model_year, warning_light, warning_light_id, and component_category. Use null for unknown scalar values, false for unknown booleans, and [] for unknown lists. severity_level: 1 informational/unknown, 2 service soon, 3 urgent service, 4 stop safely/immediate stop. recall_status_level: 0 unknown, 1 no retrieved recall candidate, 2 possible/needs vehicle details, 3 candidate recall match. Rewrite internal enum labels into human-readable text. evidence_used must contain only retrieved document or citation IDs.",

    EmptyAnswer = [
        summary = "",
        severity_label = "",
        severity_level = null,
        severity_color = "#607D8B",
        severity_icon_key = "info",
        stop_immediately = false,
        recommended_service = "",
        recall_status = "",
        recall_status_level = null,
        recall_status_color = "#607D8B",
        recall_icon_key = "recall_unknown",
        possible_causes = {},
        immediate_action = "",
        primary_campaign = null,
        recall_interpretation = "",
        evidence_used = {},
        parsed = [
            make = null,
            model = null,
            model_year = null,
            warning_light = null,
            warning_light_id = null,
            component_category = null
        ]
    ],

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

    CanonicalDocumentId = (value as nullable text) as nullable text =>
        if value = null then
            null
        else
            let
                Raw = Text.From(value),
                BeforePages = try Text.BeforeDelimiter(Raw, "_pages") otherwise Raw,
                Parts = Text.Split(BeforePages, "_"),
                Token = if List.Count(Parts) > 1 then Text.Combine(List.Skip(Parts, 1), "_") else BeforePages,
                Canonical =
                    if Text.StartsWith(Token, "recall-") then "recall:" & Text.AfterDelimiter(Token, "recall-")
                    else if Text.StartsWith(Token, "warning_light-") then "warning_light:" & Text.AfterDelimiter(Token, "warning_light-")
                    else if Text.StartsWith(Token, "maintenance_service-") then "maintenance_service:" & Text.AfterDelimiter(Token, "maintenance_service-")
                    else if Text.StartsWith(Token, "image-") then "image:" & Text.AfterDelimiter(Token, "image-")
                    else if Text.StartsWith(Token, "scenario-") then "scenario:" & Text.AfterDelimiter(Token, "scenario-")
                    else Token
            in
                Canonical,

    SourceType = (documentId as nullable text) as text =>
        if documentId = null then "AZURE_AI_SEARCH"
        else if Text.StartsWith(documentId, "recall:") then "NHTSA_RECALLS_API"
        else if Text.StartsWith(documentId, "warning_light:") then "STANDARD_64_WARNING_LIGHT_GUIDE_PLUS_OEM_REFERENCE"
        else if Text.StartsWith(documentId, "maintenance_service:") then "TEAM_STRUCTURED_SERVICE_MAP_FROM_STANDARD_64_WARNING_CATALOG"
        else if Text.StartsWith(documentId, "image:") then "WARNING_LIGHT_IMAGE_METADATA"
        else if Text.StartsWith(documentId, "scenario:") then "STANDARD_64_WARNING_LIGHT_PLUS_NHTSA_RECALL"
        else "AZURE_AI_SEARCH",

    EvidenceLevel = (documentId as nullable text) as text =>
        if documentId <> null and Text.StartsWith(documentId, "recall:") then "recall_candidate_match"
        else if documentId <> null and Text.StartsWith(documentId, "warning_light:") then "warning_light_guideline"
        else if documentId <> null and Text.StartsWith(documentId, "maintenance_service:") then "service_map_match"
        else if documentId <> null and Text.StartsWith(documentId, "scenario:") then "validation_scenario"
        else if documentId <> null and Text.StartsWith(documentId, "image:") then "image_icon_support"
        else "generic_retrieved_evidence",

    Label = (value as nullable text) as nullable text =>
        if value = null then null else Text.Proper(Text.Replace(Text.Replace(value, "_", " "), "-", " ")),

    CampaignId = (content as text) as nullable text =>
        try Text.BeforeDelimiter(Text.AfterDelimiter(content, "Campaign "), ".") otherwise null,

    ParseAnswer = (content as text) as record =>
        let
            Parsed = try Json.Document(Text.ToBinary(content)) otherwise null
        in
            if Parsed is record then Parsed else Record.Combine({EmptyAnswer, [summary = content]}),

    NormalizeCitation = (citation as record, index as number) as record =>
        let
            Content = try Text.From(citation[content]) otherwise "",
            Url = try Text.From(citation[url]) otherwise null,
            Title = try Text.From(citation[title]) otherwise null,
            Filepath = try Text.From(citation[filepath]) otherwise null,
            ChunkId = try Text.From(citation[chunk_id]) otherwise null,
            DocumentId = CanonicalDocumentId(FirstNonNull({ChunkId, Filepath, Title}, "azure-citation-" & Text.From(index))),
            Source = SourceType(DocumentId),
            Level = EvidenceLevel(DocumentId)
        in
            [
                score = null,
                document_id = DocumentId,
                source_type = Source,
                source_type_label = Label(Source),
                source_id = if DocumentId <> null and Text.Contains(DocumentId, ":") then Text.AfterDelimiter(DocumentId, ":") else DocumentId,
                rank = index,
                confidence_label = "Unscored",
                evidence_level = Level,
                evidence_level_label = Label(Level),
                warning_light_id = null,
                warning_light_name = null,
                make = null,
                model = null,
                model_year = null,
                campaign_id = CampaignId(Content),
                recall_relevance = if DocumentId <> null and Text.StartsWith(DocumentId, "recall:") then "candidate_match" else null,
                recall_relevance_label = if DocumentId <> null and Text.StartsWith(DocumentId, "recall:") then "Candidate recall match" else null,
                component_category = null,
                severity = null,
                severity_label = null,
                recommended_service_type = null,
                recommended_service_label = null,
                source_url = Url,
                image_path = null,
                review_status = null,
                content_preview = Text.Start(Content, 240),
                rank_score = null,
                match_reasons = {}
            ],

    AzureQuery = (
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
        optional filter as nullable text,
        optional roleInformation as nullable text
    ) as record =>
        let
            Prompt = Text.Trim(query),
            Version = if apiVersion = null then "2024-05-01-preview" else apiVersion,
            RoleInformation = if roleInformation = null then DefaultRoleInformation else roleInformation,
            Endpoint = NormalizeEndpoint(azureOpenAIEndpoint),
            SearchParametersBase = [
                endpoint = NormalizeEndpoint(searchEndpoint),
                index_name = searchIndex,
                authentication = [type = "api_key", key = searchKey],
                top_n_documents = if topK = null then 5 else Int64.From(topK),
                strictness = if strictness = null then 3 else Int64.From(strictness),
                query_type = if queryType = null then "simple" else queryType,
                in_scope = true,
                role_information = RoleInformation
            ],
            SearchParametersWithEmbedding =
                if embeddingDeployment = null then SearchParametersBase
                else Record.Combine({SearchParametersBase, [embedding_dependency = [type = "deployment_name", deployment_name = embeddingDeployment]]}),
            SearchParametersWithSemantic =
                if semanticConfiguration = null then SearchParametersWithEmbedding
                else Record.Combine({SearchParametersWithEmbedding, [semantic_configuration = semanticConfiguration]}),
            SearchParameters =
                if filter = null then SearchParametersWithSemantic
                else Record.Combine({SearchParametersWithSemantic, [filter = filter]}),
            Response =
                if Prompt = "" then
                    null
                else
                    Json.Document(
                        Web.Contents(
                            Endpoint,
                            [
                                RelativePath = "openai/deployments/" & chatDeployment & "/chat/completions",
                                Query = [#"api-version" = Version],
                                Headers = [#"Content-Type" = "application/json", #"api-key" = azureOpenAIKey],
                                Content = Json.FromValue([
                                    messages = {[role = "user", content = Prompt]},
                                    temperature = 0,
                                    data_sources = {[type = "azure_search", parameters = SearchParameters]}
                                ])
                            ]
                        )
                    ),
            Message = if Response = null then null else Response[choices]{0}[message],
            Content = if Message = null then "" else Text.From(Message[content]),
            Context = if Message = null then null else try Message[context] otherwise null,
            Citations = if Context = null then {} else try Context[citations] otherwise {},
            Evidence = List.Transform(List.Positions(Citations), each NormalizeCitation(Citations{_}, _ + 1))
        in
            [
                query = Prompt,
                answer = if Prompt = "" then EmptyAnswer else ParseAnswer(Content),
                evidence = Evidence,
                raw = Response
            ]
in
    AzureQuery
