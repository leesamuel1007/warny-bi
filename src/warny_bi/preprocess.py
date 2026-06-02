"""Preprocessing containers for SQL-ready WARNY-BI CSV outputs."""

from __future__ import annotations

import json
from pathlib import Path
import re

from warny_bi.io import CsvHandler
from warny_bi.validate import DatasetSchemaReporter


class DatasetPreprocessor:
    """Converts raw CSV files into processed SQL-ready CSV files."""

    def __init__(self, csv_handler: CsvHandler, raw_dir: Path, processed_dir: Path, image_dir: Path) -> None:
        self.csv_handler = csv_handler
        self.raw_dir = raw_dir
        self.processed_dir = processed_dir
        self.image_dir = image_dir

    def run(self, schema_path: Path | None = None) -> dict[str, object]:
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        schema = self.load_schema(schema_path) if schema_path else None
        written_files = []
        for raw_path in sorted(self.raw_dir.glob("*.csv")):
            source = CsvHandler().read(raw_path)
            table_schema = self.table_schema(schema, raw_path.name)
            cleaned_rows = [self.clean_row(row, table_schema) for row in source.rows]
            columns = self.output_columns(source, table_schema)
            output_path = self.processed_dir / raw_path.name
            CsvHandler(output_path).set_rows(cleaned_rows, columns).write()
            written_files.append(output_path.name)

        generated_schema = DatasetSchemaReporter(self.csv_handler).build_schema(self.processed_dir)
        generated_schema_path = self.processed_dir / "schema.json"
        generated_schema_path.write_text(DatasetSchemaReporter(self.csv_handler).to_json(generated_schema), encoding="utf-8")
        return {"processed_files": written_files, "schema_file": generated_schema_path.as_posix()}

    def load_schema(self, schema_path: Path) -> dict[str, object]:
        return json.loads(schema_path.read_text(encoding="utf-8"))

    def table_schema(self, schema: dict[str, object] | None, file_name: str) -> dict[str, object] | None:
        if not schema:
            return None
        for table in schema.get("tables", []):
            if isinstance(table, dict) and table.get("file") == file_name:
                return table
        return None

    def output_columns(self, source: CsvHandler, table_schema: dict[str, object] | None) -> list[str]:
        if table_schema:
            columns = table_schema.get("columns", [])
            if isinstance(columns, list):
                names = [column.get("name") for column in columns if isinstance(column, dict)]
                if all(isinstance(name, str) for name in names):
                    return names
        return source.columns

    def clean_row(self, row: dict[str, str], table_schema: dict[str, object] | None) -> dict[str, str]:
        return {
            column: self.clean_value(value, self.column_rules(table_schema, column))
            for column, value in row.items()
        }

    def column_rules(self, table_schema: dict[str, object] | None, column_name: str) -> list[str]:
        if table_schema:
            for column in table_schema.get("columns", []):
                if isinstance(column, dict) and column.get("name") == column_name:
                    rules = column.get("normalization", [])
                    if isinstance(rules, list) and all(isinstance(rule, str) for rule in rules):
                        return rules
        return ["trim", "collapse_spaces"]

    def clean_value(self, value: str | None, rules: list[str]) -> str:
        cleaned = value or ""
        for rule in rules:
            cleaned = self.apply_rule(cleaned, rule)
        return cleaned

    def apply_rule(self, value: str, rule: str) -> str:
        if rule == "trim":
            return value.strip()
        if rule == "collapse_spaces":
            return re.sub(r"\s+", " ", value)
        if rule == "uppercase":
            return value.upper()
        if rule == "remove_punctuation_except_period":
            return self.remove_punctuation_except_period(value)
        if rule == "spaces_to_underscore":
            return value.replace(" ", "_")
        if rule == "normalize_slashes":
            return value.replace("\\", "/")
        if rule == "boolean_text":
            return self.boolean_text(value)
        return value

    def boolean_text(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return "TRUE"
        if normalized in {"false", "f", "no", "n", "0"}:
            return "FALSE"
        return value

    def remove_punctuation_except_period(self, value: str) -> str:
        without_punctuation = re.sub(r"[^\w\s.]", " ", value)
        return re.sub(r"\s+", " ", without_punctuation).strip()
