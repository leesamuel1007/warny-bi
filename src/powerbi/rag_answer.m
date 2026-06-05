let
    FieldOrNull = (recordValue as nullable record, fieldName as text) as any =>
        if recordValue is record then
            try Record.Field(recordValue, fieldName) otherwise null
        else
            null,

    FieldOrText = (recordValue as record, fieldName as text) as text =>
        let
            Value = try Record.Field(recordValue, fieldName) otherwise ""
        in
            Text.From(Value),

    RagAnswer = (response as record) as table =>
        let
            ParsedIntent = try response[parsed_intent] otherwise null,
            AnswerRecord = [
                query = FieldOrText(response, "query"),
                answer = FieldOrText(response, "answer"),
                parsed_make = FieldOrNull(ParsedIntent, "make"),
                parsed_model = FieldOrNull(ParsedIntent, "model"),
                parsed_model_year = FieldOrNull(ParsedIntent, "model_year"),
                parsed_warning_light = FieldOrNull(ParsedIntent, "warning_light")
            ],
            AnswerTable = Table.FromRecords({AnswerRecord})
        in
            AnswerTable
in
    RagAnswer
