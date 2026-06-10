"""Prompt helpers for the Azure bridge."""

from __future__ import annotations

from pathlib import Path


DEFAULT_ROLE_INFORMATION = (
    "You are WARNY-BI, a vehicle warning-light triage assistant for a Power BI dashboard. "
    "Use only retrieved evidence. Do not claim a confirmed diagnosis. Separate warning-light "
    "guidance from recall applicability. Say when VIN lookup, OEM manual review, or professional "
    "service inspection is required. Return exactly one JSON object. Do not include Markdown, "
    "code fences, comments, or extra text. Always include these keys: summary, severity_label, "
    "severity_level, severity_color, severity_icon_key, stop_immediately, recommended_service, "
    "recall_status, recall_status_level, recall_status_color, recall_icon_key, possible_causes, "
    "immediate_action, primary_campaign, recall_interpretation, evidence_used, parsed. The parsed "
    "object must include make, model, model_year, warning_light, warning_light_id, and "
    "component_category. Use null for unknown scalar values, false for unknown booleans, and [] "
    "for unknown lists. Rewrite internal enum labels into human-readable Power BI text."
)


class RoleInformationReader:
    """Loads Azure OpenAI role instructions from the shared prompt file."""

    def __init__(self, explicit_text: str | None, prompt_path: Path | None) -> None:
        self.explicit_text = explicit_text
        self.prompt_path = prompt_path

    def read(self) -> str:
        if self.explicit_text and self.explicit_text.strip():
            return self.explicit_text.strip()
        if self.prompt_path and self.prompt_path.is_file():
            return self.role_information_from_template(self.prompt_path.read_text(encoding="utf-8"))
        return DEFAULT_ROLE_INFORMATION

    def role_information_from_template(self, template: str) -> str:
        before_user_query = template.split("User query:", 1)[0].strip()
        return before_user_query or DEFAULT_ROLE_INFORMATION
