"""Validation and schema reporting containers for WARNY-BI."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from warny_bi.eda import TableProfiler
from warny_bi.io import CsvHandler


@dataclass(frozen=True)
class ValidationResult:
    """Result of lightweight dataset checks."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.errors


class DatasetValidator:
    """Checks that static CSV and image inputs are present."""

    def __init__(self, csv_handler: CsvHandler, raw_dir: Path, image_dir: Path) -> None:
        self.csv_handler = csv_handler
        self.raw_dir = raw_dir
        self.image_dir = image_dir

    def run(self) -> ValidationResult:
        errors: list[str] = []
        warnings: list[str] = []
        csv_paths = sorted(self.raw_dir.glob("*.csv"))
        if not csv_paths:
            errors.append(f"No raw CSV files found under {self.raw_dir}")
        if not self.image_dir.exists():
            errors.append(f"Image directory does not exist: {self.image_dir}")

        for path in csv_paths:
            rows = CsvHandler().read(path).rows
            if not rows:
                warnings.append(f"{path.name}: no data rows")
            elif not rows[0]:
                warnings.append(f"{path.name}: no columns")

        image_catalog = self.raw_dir / "warning_light_image_catalog.csv"
        if image_catalog.exists():
            errors.extend(self.missing_image_path_errors(image_catalog))
        return ValidationResult(errors=tuple(errors), warnings=tuple(warnings))

    def missing_image_path_errors(self, image_catalog: Path) -> list[str]:
        errors = []
        rows = CsvHandler().read(image_catalog).rows
        for row in rows:
            image_file = row.get("image_file", "").strip()
            if image_file and not (self.raw_dir.parent.parent / image_file).exists():
                errors.append(f"{image_catalog.name}: missing image file {image_file}")
            if not image_file:
                errors.append(f"{image_catalog.name}: blank image_file for {row.get('image_id', '<unknown>')}")
        return errors[:25]


class DatasetSchemaReporter:
    """Generates operator-reviewable schema JSON from actual CSV files."""

    def __init__(self, csv_handler: CsvHandler, table_profiler: TableProfiler | None = None) -> None:
        self.csv_handler = csv_handler
        self.table_profiler = table_profiler or TableProfiler()

    def build_schema(self, csv_dir: Path) -> dict[str, object]:
        tables = []
        for path in sorted(csv_dir.glob("*.csv")):
            if path.name == "schema.json":
                continue
            rows = CsvHandler().read(path).rows
            columns = list(rows[0].keys()) if rows else []
            primary_key = self.infer_primary_key(columns, rows)
            tables.append(
                {
                    "file": path.name,
                    "table_name": path.stem,
                    "row_count": len(rows),
                    "columns": [
                        self.column_schema(column, rows, primary_key)
                        for column in columns
                    ],
                    "primary_key": primary_key,
                    "foreign_keys": self.infer_foreign_keys(path.stem, columns),
                }
            )
        return {
            "source": "generated_from_csv",
            "operator_review_required": True,
            "tables": tables,
        }

    def to_json(self, schema: dict[str, object]) -> str:
        return json.dumps(schema, indent=2, ensure_ascii=False)

    def column_schema(self, column: str, rows: list[dict[str, str]], primary_key: str | None) -> dict[str, object]:
        profile = self.table_profiler.profile_column(column, rows)
        preferred_type = self.preferred_type(column, profile.inferred_type)
        return {
            "name": column,
            "inferred_type": profile.inferred_type,
            "preferred_type": preferred_type,
            "suggested_sql_type": self.infer_sql_type(column, rows, preferred_type),
            "blank_count": profile.blank_count,
            "null_like_count": profile.null_like_count,
            "unique_count": profile.unique_count,
            "primary_key": column == primary_key,
            "normalization": self.normalization_rules(column, preferred_type),
        }

    def infer_primary_key(self, columns: list[str], rows: list[dict[str, str]]) -> str | None:
        for column in columns:
            if not column.endswith("_id"):
                continue
            values = [row.get(column, "").strip() for row in rows]
            if values and all(values) and len(set(values)) == len(values):
                return column
        return None

    def infer_foreign_keys(self, table_name: str, columns: list[str]) -> list[dict[str, str]]:
        foreign_keys = []
        for column in columns:
            if column == "warning_light_id" and table_name != "warning_light_catalog":
                foreign_keys.append(
                    {
                        "column": column,
                        "references_table": "warning_light_catalog",
                        "references_column": "warning_light_id",
                        "status": "inferred",
                    }
                )
            if column == "related_warning_light_id":
                foreign_keys.append(
                    {
                        "column": column,
                        "references_table": "warning_light_catalog",
                        "references_column": "warning_light_id",
                        "status": "inferred",
                    }
                )
        return foreign_keys

    def preferred_type(self, column: str, inferred_type: str) -> str:
        if column.endswith("_id") or column in {"image_id", "source_id", "scenario_id", "campaign_id"}:
            return "identifier"
        if "path" in column or "file" in column or column.endswith("_url_or_blob_path"):
            return "path"
        if column.startswith("is_"):
            return "boolean"
        if inferred_type in {"integer", "decimal", "boolean"}:
            return inferred_type
        if self.is_category_column(column):
            return "category"
        return "text"

    def normalization_rules(self, column: str, preferred_type: str) -> list[str]:
        rules = ["trim", "collapse_spaces"]
        if preferred_type == "identifier":
            return rules + ["uppercase", "remove_punctuation_except_period", "spaces_to_underscore"]
        if preferred_type == "path":
            return rules + ["normalize_slashes"]
        if preferred_type == "boolean":
            return rules + ["boolean_text"]
        if preferred_type == "category":
            return rules + ["uppercase", "remove_punctuation_except_period", "spaces_to_underscore"]
        return rules

    def is_category_column(self, column: str) -> bool:
        return column in {
            "business_user",
            "color",
            "component",
            "component_category",
            "evidence_level_required",
            "expected_output_format",
            "expected_recall_relevance",
            "expected_service_type",
            "expected_severity",
            "file_ext",
            "label_confidence",
            "mapping_status",
            "recommended_service_type",
            "review_status",
            "severity",
            "severity_override",
            "source_type",
            "urgency_level",
            "warning_light_color",
        }

    def infer_sql_type(self, column: str, rows: list[dict[str, str]], preferred_type: str) -> str:
        values = [row.get(column, "").strip() for row in rows if row.get(column, "").strip()]
        if preferred_type == "integer":
            return "INT"
        if preferred_type == "decimal":
            return "FLOAT"
        if preferred_type == "boolean":
            return "BIT"
        if not values:
            return "NVARCHAR(255)"
        max_length = max(len(value) for value in values)
        if preferred_type == "identifier":
            return "NVARCHAR(50)"
        if max_length <= 50:
            return "NVARCHAR(50)"
        if max_length <= 255:
            return "NVARCHAR(255)"
        return "NVARCHAR(MAX)"
