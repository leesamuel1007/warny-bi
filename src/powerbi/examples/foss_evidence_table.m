let
    Response = WarnyRagQuery(
        "For a 2020 Hyundai Elantra with a yellow engine light, show recall relevance, urgency, recommended service, and evidence.",
        5,
        false
    ),
    EvidenceList = Response[evidence],
    EvidenceTable =
        if List.Count(EvidenceList) = 0 then
            #table(
                {
                    "score", "document_id", "source_type", "source_id",
                    "warning_light_id", "warning_light_name", "make", "model",
                    "model_year", "component_category", "severity",
                    "recommended_service_type", "source_url", "image_path",
                    "review_status", "content_preview", "rank_score",
                    "match_reasons"
                },
                {}
            )
        else
            Table.FromRecords(EvidenceList),
    CleanEvidence =
        if Table.HasColumns(EvidenceTable, "match_reasons") then
            Table.TransformColumns(
                EvidenceTable,
                {
                    {
                        "match_reasons",
                        each if _ is list then Text.Combine(List.Transform(_, Text.From), ", ") else Text.From(_),
                        type text
                    }
                }
            )
        else
            EvidenceTable
in
    CleanEvidence
