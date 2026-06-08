let
    EvidenceColumns = {
        "score", "document_id", "source_type", "source_type_label",
        "source_id", "rank", "confidence_label", "evidence_level",
        "evidence_level_label", "warning_light_id", "warning_light_name",
        "make", "model", "model_year", "campaign_id", "recall_relevance",
        "recall_relevance_label", "component_category", "severity",
        "severity_label", "recommended_service_type",
        "recommended_service_label", "source_url", "image_path",
        "review_status", "content_preview", "rank_score", "match_reasons"
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

    EvidenceResponse = (response as record) as table =>
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
            CleanReasons = Table.TransformColumns(
                WithStableColumns,
                {{"match_reasons", each NormalizeMatchReasons(_), type nullable text}}
            ),
            WithIndex = Table.AddIndexColumn(CleanReasons, "_row_rank", 1, 1, Int64.Type),
            WithFilledRank = Table.AddColumn(
                WithIndex,
                "_rank",
                each if [rank] = null then [_row_rank] else [rank],
                Int64.Type
            ),
            WithoutRank = Table.RemoveColumns(WithFilledRank, {"rank", "_row_rank"}),
            WithRank = Table.RenameColumns(WithoutRank, {{"_rank", "rank"}}),
            Ordered = Table.ReorderColumns(WithRank, EvidenceColumns, MissingField.UseNull)
        in
            Ordered
in
    EvidenceResponse
