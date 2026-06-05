let
    DefaultWarnyApiBaseUrl = "http://127.0.0.1:18080",

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
        let
            RawPayload = [
                query = query,
                top_k = if topK = null then 5 else Int64.From(topK),
                include_image_evidence = if includeImageEvidence = null then false else includeImageEvidence
            ],
            NonNullFields = List.Select(
                Record.FieldNames(RawPayload),
                each Record.Field(RawPayload, _) <> null
            )
        in
            Record.SelectFields(RawPayload, NonNullFields),

    WarnyRagQuery = (
        query as text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical,
        optional apiBaseUrl as nullable text
    ) as record =>
        let
            BaseUrl = if apiBaseUrl = null then DefaultWarnyApiBaseUrl else apiBaseUrl,
            Payload = BuildPayload(
                query,
                topK,
                includeImageEvidence
            ),
            Response = Json.Document(
                Web.Contents(
                    NormalizeEndpoint(BaseUrl),
                    [
                        RelativePath = "query",
                        Headers = [#"Content-Type" = "application/json"],
                        Content = Json.FromValue(Payload)
                    ]
                )
            )
        in
            [
                query = Response[query],
                parsed_intent = try Response[parsed_intent] otherwise null,
                answer = Response[answer],
                evidence = try Response[evidence] otherwise {},
                raw = Response
            ]
in
    WarnyRagQuery
