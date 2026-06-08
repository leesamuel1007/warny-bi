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

    FossQuery = (
        query as text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical,
        optional apiBaseUrl as nullable text
    ) as record =>
        let
            Prompt = Text.Trim(query),
            BaseUrl = if apiBaseUrl = null then "http://localhost:18080" else apiBaseUrl,
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
                            NormalizeEndpoint(BaseUrl),
                            [
                                RelativePath = "query",
                                Headers = [#"Content-Type" = "application/json"],
                                Content = Json.FromValue(BuildPayload(Prompt, topK, includeImageEvidence))
                            ]
                        )
                    )
        in
            [
                query = try Response[query] otherwise Prompt,
                answer = try Response[answer] otherwise EmptyAnswer,
                evidence = try Response[evidence] otherwise {},
                raw = Response
            ]
in
    FossQuery
