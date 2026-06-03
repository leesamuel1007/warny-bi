let
    Response = WarnyRagQuery(
        "yellow engine light recall",
        "Hyundai",
        "Elantra",
        2020,
        "engine light",
        5,
        false
    ),
    AnswerTable = Table.FromRecords({
        [
            query = Text.From(Response[query]),
            answer = Text.From(Response[answer])
        ]
    })
in
    AnswerTable