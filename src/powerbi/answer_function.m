let
    AnswerColumns = {
        "user_prompt", "answer_summary", "severity", "severity_level",
        "severity_color", "severity_icon_key", "stop_immediately",
        "recommended_service", "recall_status", "recall_status_level",
        "recall_status_color", "recall_icon_key", "possible_causes",
        "immediate_action", "primary_campaign", "recall_interpretation",
        "evidence_used", "parsed_make", "parsed_model", "parsed_model_year",
        "parsed_warning_light", "warning_light_id", "component_category",
        "evidence_count", "recall_candidate_count", "warning_guide_count",
        "service_map_count", "validation_scenario_count", "image_support_count"
    },

    FieldOrNull = (recordValue as nullable record, fieldName as text) as any =>
        if recordValue is record then try Record.Field(recordValue, fieldName) otherwise null else null,

    TextFromNullable = (value as any) as nullable text =>
        if value = null then null else Text.From(value),

    TextList = (value as any) as text =>
        if value is list then
            Text.Combine(List.Transform(value, each Text.From(_)), "; ")
        else if value = null then
            ""
        else
            Text.From(value),

    CountEvidenceLevel = (evidence as list, level as text) as number =>
        List.Count(
            List.Select(
                evidence,
                each try Record.Field(_, "evidence_level") = level otherwise false
            )
        ),

    CountSourcePrefix = (evidence as list, prefix as text) as number =>
        List.Count(
            List.Select(
                evidence,
                each try Text.StartsWith(Text.From(Record.Field(_, "document_id")), prefix) otherwise false
            )
        ),

    FirstRecallCampaign = (evidence as list) as nullable text =>
        let
            Campaigns = List.RemoveNulls(List.Transform(evidence, each try Record.Field(_, "campaign_id") otherwise null))
        in
            if List.Count(Campaigns) = 0 then null else Text.From(Campaigns{0}),

    FirstNonNull = (values as list) as any =>
        let
            NonNullValues = List.RemoveNulls(values)
        in
            if List.Count(NonNullValues) = 0 then null else NonNullValues{0},

    AnswerResponse = (response as record) as table =>
        let
            Answer = try response[answer] otherwise [],
            Parsed = FieldOrNull(Answer, "parsed"),
            Evidence = try response[evidence] otherwise {},
            EvidenceList = if Evidence is list then Evidence else {},
            Row = [
                user_prompt = TextFromNullable(try response[query] otherwise null),
                answer_summary = TextFromNullable(FieldOrNull(Answer, "summary")),
                severity = TextFromNullable(FieldOrNull(Answer, "severity_label")),
                severity_level = FieldOrNull(Answer, "severity_level"),
                severity_color = TextFromNullable(FieldOrNull(Answer, "severity_color")),
                severity_icon_key = TextFromNullable(FieldOrNull(Answer, "severity_icon_key")),
                stop_immediately = FieldOrNull(Answer, "stop_immediately"),
                recommended_service = TextFromNullable(FieldOrNull(Answer, "recommended_service")),
                recall_status = TextFromNullable(FieldOrNull(Answer, "recall_status")),
                recall_status_level = FieldOrNull(Answer, "recall_status_level"),
                recall_status_color = TextFromNullable(FieldOrNull(Answer, "recall_status_color")),
                recall_icon_key = TextFromNullable(FieldOrNull(Answer, "recall_icon_key")),
                possible_causes = TextList(FieldOrNull(Answer, "possible_causes")),
                immediate_action = TextFromNullable(FieldOrNull(Answer, "immediate_action")),
                primary_campaign = TextFromNullable(FirstNonNull({FieldOrNull(Answer, "primary_campaign"), FirstRecallCampaign(EvidenceList)})),
                recall_interpretation = TextFromNullable(FieldOrNull(Answer, "recall_interpretation")),
                evidence_used = TextList(FieldOrNull(Answer, "evidence_used")),
                parsed_make = TextFromNullable(FieldOrNull(Parsed, "make")),
                parsed_model = TextFromNullable(FieldOrNull(Parsed, "model")),
                parsed_model_year = FieldOrNull(Parsed, "model_year"),
                parsed_warning_light = TextFromNullable(FieldOrNull(Parsed, "warning_light")),
                warning_light_id = TextFromNullable(FieldOrNull(Parsed, "warning_light_id")),
                component_category = TextFromNullable(FieldOrNull(Parsed, "component_category")),
                evidence_count = List.Count(EvidenceList),
                recall_candidate_count = CountSourcePrefix(EvidenceList, "recall:"),
                warning_guide_count = CountEvidenceLevel(EvidenceList, "warning_light_guideline"),
                service_map_count = CountEvidenceLevel(EvidenceList, "service_map_match"),
                validation_scenario_count = CountEvidenceLevel(EvidenceList, "validation_scenario"),
                image_support_count = CountEvidenceLevel(EvidenceList, "image_icon_support")
            ],
            AnswerTable = Table.FromRecords({Row}),
            StableColumns = Table.SelectColumns(AnswerTable, AnswerColumns, MissingField.UseNull)
        in
            StableColumns
in
    AnswerResponse
