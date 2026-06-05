let
    EvidenceColumns = {
        "score", "document_id", "source_type", "source_id",
        "warning_light_id", "warning_light_name", "make", "model",
        "model_year", "component_category", "severity",
        "recommended_service_type", "source_url", "image_path",
        "review_status", "content_preview", "rank_score",
        "match_reasons"
    },

    EmptyEvidenceTable = () as table =>
        #table(EvidenceColumns, {}),

    TextFromNullable = (value as any) as nullable text =>
        if value = null then null else Text.From(value),

    NormalizeMatchReasons = (value as any) as nullable text =>
        if value is list then
            Text.Combine(List.Transform(value, each Text.From(_)), ", ")
        else
            TextFromNullable(value),

    RagEvidence = (response as record) as table =>
        let
            EvidenceList = try response[evidence] otherwise {},
            RawEvidenceTable =
                if not (EvidenceList is list) or List.Count(EvidenceList) = 0 then
                    EmptyEvidenceTable()
                else
                    Table.FromRecords(EvidenceList),
            WithStableColumns = Table.SelectColumns(
                RawEvidenceTable,
                EvidenceColumns,
                MissingField.UseNull
            ),
            CleanEvidence =
                if Table.HasColumns(WithStableColumns, "match_reasons") then
                    Table.TransformColumns(
                        WithStableColumns,
                        {{"match_reasons", each NormalizeMatchReasons(_), type nullable text}}
                    )
                else
                    WithStableColumns
        in
            CleanEvidence
in
    RagEvidence
