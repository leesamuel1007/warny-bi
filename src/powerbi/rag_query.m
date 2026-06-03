let
    WarnyApiBaseUrl = "http://127.0.0.1:18080",

    BuildPayload = (
        query as text,
        optional make as nullable text,
        optional model as nullable text,
        optional modelYear as nullable number,
        optional warningLight as nullable text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical
    ) as record =>
        let
            RawPayload = [
                query = query,
                make = make,
                model = model,
                model_year = if modelYear = null then null else Int64.From(modelYear),
                warning_light = warningLight,
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
        optional make as nullable text,
        optional model as nullable text,
        optional modelYear as nullable number,
        optional warningLight as nullable text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical
    ) as record =>
        let
            Payload = BuildPayload(
                query,
                make,
                model,
                modelYear,
                warningLight,
                topK,
                includeImageEvidence
            ),
            Response = Json.Document(
                Web.Contents(
                    WarnyApiBaseUrl,
                    [
                        RelativePath = "query",
                        Headers = [#"Content-Type" = "application/json"],
                        Content = Json.FromValue(Payload)
                    ]
                )
            )
        in
            Response
in
    WarnyRagQuery
