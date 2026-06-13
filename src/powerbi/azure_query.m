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

    TextOrNull = (value as any) as nullable text =>
        if value = null then
            null
        else
            let
                TextValue = Text.Trim(Text.From(value))
            in
                if TextValue = "" then null else TextValue,

    FieldOrNull = (recordValue as any, fieldName as text) as any =>
        if recordValue is record then try Record.Field(recordValue, fieldName) otherwise null else null,

    ParseJsonRecord = (value as any, fallback as record) as record =>
        if value is record then
            value
        else if value is text and Text.Trim(value) <> "" then
            let
                Parsed = try Json.Document(value) otherwise fallback
            in
                if Parsed is record then Parsed else fallback
        else
            fallback,

    TokenAfter = (textValue as nullable text, marker as text, optional includeMarker as nullable logical) as nullable text =>
        let
            SourceText = if textValue = null then "" else textValue,
            Position = Text.PositionOf(SourceText, marker, Occurrence.First),
            IncludePrefix = if includeMarker = null then false else includeMarker
        in
            if Position < 0 then
                null
            else
                let
                    Tail = Text.Range(SourceText, Position + Text.Length(marker)),
                    Delimiters = {" ", "#(lf)", "#(cr)", ".", ",", ";", ")", "(", "]", "["},
                    Positions = List.RemoveItems(List.Transform(Delimiters, each Text.PositionOf(Tail, _, Occurrence.First)), {-1}),
                    EndPosition = if List.Count(Positions) = 0 then Text.Length(Tail) else List.Min(Positions),
                    Token = Text.Start(Tail, EndPosition)
                in
                    if Token = "" then null else if IncludePrefix then marker & Token else Token,

    FirstNonNull = (values as list) as any =>
        let
            NonNullValues = List.RemoveNulls(values)
        in
            if List.Count(NonNullValues) = 0 then null else NonNullValues{0},

    SourceTypeFromDocument = (documentId as nullable text) as text =>
        if documentId <> null and Text.StartsWith(documentId, "recall:") then
            "NHTSA_RECALLS_API"
        else if documentId <> null and Text.StartsWith(documentId, "warning_light:") then
            "STANDARD_64_WARNING_LIGHT_GUIDE_PLUS_OEM_REFERENCE"
        else if documentId <> null and Text.StartsWith(documentId, "maintenance_service:") then
            "TEAM_STRUCTURED_SERVICE_MAP_FROM_STANDARD_64_WARNING_CATALOG"
        else if documentId <> null and Text.StartsWith(documentId, "scenario:") then
            "STANDARD_64_WARNING_LIGHT_PLUS_NHTSA_RECALL"
        else if documentId <> null and Text.StartsWith(documentId, "image:") then
            "WARNING_LIGHT_IMAGE_METADATA"
        else
            "AZURE_AI_SEARCH",

    EvidenceLevelFromDocument = (documentId as nullable text) as text =>
        if documentId <> null and Text.StartsWith(documentId, "recall:") then
            "recall_candidate_match"
        else if documentId <> null and Text.StartsWith(documentId, "warning_light:") then
            "warning_light_guideline"
        else if documentId <> null and Text.StartsWith(documentId, "maintenance_service:") then
            "service_map_match"
        else if documentId <> null and Text.StartsWith(documentId, "scenario:") then
            "validation_scenario"
        else if documentId <> null and Text.StartsWith(documentId, "image:") then
            "image_icon_support"
        else
            "azure_ai_search_citation",

    CitationToEvidence = (citation as record, index as number, answer as record) as record =>
        let
            Content = TextOrNull(FieldOrNull(citation, "content")),
            ChunkId = TextOrNull(FieldOrNull(citation, "chunk_id")),
            FilePath = TextOrNull(FieldOrNull(citation, "filepath")),
            Title = TextOrNull(FieldOrNull(citation, "title")),
            Parsed = FieldOrNull(answer, "parsed"),
            DocumentId = FirstNonNull({
                TokenAfter(Content, "recall:", true),
                TokenAfter(Content, "warning_light:", true),
                TokenAfter(Content, "maintenance_service:", true),
                TokenAfter(Content, "scenario:", true),
                TokenAfter(Content, "image:", true),
                ChunkId,
                FilePath,
                Title,
                "azure-citation-" & Text.From(index + 1)
            }),
            SourceType = SourceTypeFromDocument(DocumentId),
            EvidenceLevel = EvidenceLevelFromDocument(DocumentId)
        in
            [
                score = null,
                document_id = DocumentId,
                source_type = SourceType,
                source_type_label = if SourceType = "AZURE_AI_SEARCH" then "Azure AI Search citation" else SourceType,
                source_id = FirstNonNull({ChunkId, DocumentId}),
                rank = index + 1,
                confidence_label = "Retrieved",
                evidence_level = EvidenceLevel,
                evidence_level_label = if EvidenceLevel = "azure_ai_search_citation" then "Azure AI Search citation" else EvidenceLevel,
                warning_light_id = FirstNonNull({TokenAfter(Content, "WL", true), FieldOrNull(Parsed, "warning_light_id")}),
                warning_light_name = FieldOrNull(Parsed, "warning_light"),
                make = FieldOrNull(Parsed, "make"),
                model = FieldOrNull(Parsed, "model"),
                model_year = FieldOrNull(Parsed, "model_year"),
                campaign_id = FirstNonNull({TokenAfter(Content, "Campaign "), FieldOrNull(answer, "primary_campaign")}),
                recall_relevance = FieldOrNull(answer, "recall_status"),
                recall_relevance_label = FieldOrNull(answer, "recall_status"),
                component_category = FieldOrNull(Parsed, "component_category"),
                severity = FieldOrNull(answer, "severity_label"),
                severity_label = FieldOrNull(answer, "severity_label"),
                recommended_service_type = FieldOrNull(answer, "recommended_service"),
                recommended_service_label = FieldOrNull(answer, "recommended_service"),
                source_url = TextOrNull(FieldOrNull(citation, "url")),
                image_path = null,
                review_status = null,
                content_preview = if Content = null then null else Text.Start(Content, 240),
                rank_score = null,
                match_reasons = {}
            ],

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
        logicAppUrl as text,
        optional topK as nullable number,
        optional includeImageEvidence as nullable logical
    ) as record =>
        let
            Prompt = Text.Trim(query),
            RequestTopK = if topK = null then 5 else Int64.From(topK),
            RequestIncludeImageEvidence = if includeImageEvidence = null then false else includeImageEvidence,
            RawResponse =
                if Prompt = "" then
                    null
                else
                    Json.Document(
                        Web.Contents(
                            Text.Trim(logicAppUrl),
                            [
                                Headers = [#"Content-Type" = "application/json"],
                                Content = Json.FromValue(BuildPayload(Prompt, RequestTopK, RequestIncludeImageEvidence))
                            ]
                        )
                    ),
            Choices = if RawResponse is record then FieldOrNull(RawResponse, "choices") else null,
            FirstChoice = if Choices is list and List.Count(Choices) > 0 then Choices{0} else null,
            Message = FieldOrNull(FirstChoice, "message"),
            Context = FieldOrNull(Message, "context"),
            Answer = if Prompt = "" then EmptyAnswer else ParseJsonRecord(FieldOrNull(Message, "content"), EmptyAnswer),
            Citations = FieldOrNull(Context, "citations"),
            Evidence =
                if Citations is list then
                    List.Transform(List.Positions(Citations), each CitationToEvidence(Citations{_}, _, Answer))
                else
                    {}
        in
            [
                query = Prompt,
                top_k = RequestTopK,
                include_image_evidence = RequestIncludeImageEvidence,
                answer = Answer,
                evidence = Evidence,
                raw = RawResponse
            ]
in
    AzureQuery
