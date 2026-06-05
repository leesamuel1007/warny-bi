let
    Response = WarnyRagQuery(
        "For a 2020 Hyundai Elantra with a yellow engine light, show recall relevance, urgency, recommended service, and evidence.",
        5,
        false
    ),
    CleanEvidence = RagEvidence(Response)
in
    CleanEvidence
