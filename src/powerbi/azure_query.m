let
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

    TextOrNull = (value as nullable text) as nullable text =>
        if value = null or Text.Trim(value) = "" then null else Text.Trim(value),

    BuildHeaders = (optional functionKey as nullable text) as record =>
        let
            BaseHeaders = [#"Content-Type" = "application/json"],
            CleanKey = TextOrNull(functionKey)
        in
            if CleanKey = null then BaseHeaders else Record.Combine({BaseHeaders, [#"x-functions-key" = CleanKey]}),

    BuildPayload = (
        query as text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical
    ) as record =>
        [
            query = query,
            top_k = if topK = null then 5 else Int64.From(topK),
            include_image_evidence = if includeImageEvidence = null then false else includeImageEvidence
        ],

    AzureQuery = (
        query as text,
        azureBridgeBaseUrl as text,
        optional azureBridgeFunctionKey as nullable text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical
    ) as record =>
        let
            Prompt = Text.Trim(query),
            Response =
                if Prompt = "" then
                    [
                        query = "",
                        answer = EmptyAnswer,
                        evidence = {},
                        raw = null
                    ]
                else
                    Json.Document(
                        Web.Contents(
                            NormalizeEndpoint(azureBridgeBaseUrl),
                            [
                                RelativePath = "api/query",
                                Headers = BuildHeaders(azureBridgeFunctionKey),
                                Content = Json.FromValue(BuildPayload(Prompt, topK, includeImageEvidence))
                            ]
                        )
                    )
        in
            [
                query = try Response[query] otherwise Prompt,
                answer = try Response[answer] otherwise EmptyAnswer,
                evidence = try Response[evidence] otherwise {},
                query_id = try Response[query_id] otherwise null,
                logging_status = try Response[logging_status] otherwise null,
                raw = Response
            ]
in
    AzureQuery
