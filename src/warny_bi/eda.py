"""Table-agnostic EDA containers for WARNY-BI CSV data."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from warny_bi.io import CsvHandler


@dataclass(frozen=True)
class ColumnProfile:
    """Summary for one CSV column."""

    name: str
    blank_count: int
    null_like_count: int
    unique_count: int
    inferred_type: str
    top_values: dict[str, int]


@dataclass(frozen=True)
class TableProfile:
    """Summary for one CSV table."""

    file: str
    rows: int
    columns: tuple[str, ...]
    column_profiles: tuple[ColumnProfile, ...]


class TableProfiler:
    """Profiles one table without project-specific assumptions."""

    def __init__(self, low_cardinality_limit: int = 20, top_value_limit: int = 10) -> None:
        self.low_cardinality_limit = low_cardinality_limit
        self.top_value_limit = top_value_limit

    def profile(self, file_name: str, rows: list[dict[str, str]]) -> TableProfile:
        columns = tuple(rows[0].keys()) if rows else tuple()
        return TableProfile(
            file=file_name,
            rows=len(rows),
            columns=columns,
            column_profiles=tuple(self.profile_column(column, rows) for column in columns),
        )

    def profile_column(self, column: str, rows: list[dict[str, str]]) -> ColumnProfile:
        values = [row.get(column, "") for row in rows]
        stripped_values = [value.strip() for value in values]
        non_null_values = [value for value in stripped_values if not self.is_null_like(value)]
        counts = Counter(non_null_values)
        top_values = {}
        if len(counts) <= self.low_cardinality_limit:
            top_values = dict(counts.most_common(self.top_value_limit))
        return ColumnProfile(
            name=column,
            blank_count=sum(1 for value in stripped_values if not value),
            null_like_count=sum(1 for value in stripped_values if self.is_null_like(value)),
            unique_count=len(counts),
            inferred_type=self.infer_type(non_null_values),
            top_values=top_values,
        )

    def infer_type(self, values: list[str]) -> str:
        if not values:
            return "unknown"
        if all(self.is_integer(value) for value in values):
            return "integer"
        if all(self.is_float(value) for value in values):
            return "decimal"
        if all(self.is_boolean(value) for value in values):
            return "boolean"
        unique_values = {value for value in values}
        if len(unique_values) <= self.low_cardinality_limit:
            return "category"
        return "text"

    def is_null_like(self, value: str) -> bool:
        return value.strip().lower() in {"", "na", "n/a", "nan", "null", "none"}

    def is_integer(self, value: str) -> bool:
        try:
            int(value)
        except ValueError:
            return False
        return True

    def is_float(self, value: str) -> bool:
        try:
            float(value)
        except ValueError:
            return False
        return True

    def is_boolean(self, value: str) -> bool:
        return value.strip().lower() in {"true", "false", "t", "f", "yes", "no", "y", "n", "1", "0"}


class DatasetProfiler:
    """Profiles every CSV file in a directory."""

    def __init__(self, csv_handler: CsvHandler, table_profiler: TableProfiler | None = None) -> None:
        self.csv_handler = csv_handler
        self.table_profiler = table_profiler or TableProfiler()

    def profile_directory(self, csv_dir: Path) -> tuple[TableProfile, ...]:
        return tuple(
            self.table_profiler.profile(path.name, CsvHandler().read(path).rows)
            for path in sorted(csv_dir.glob("*.csv"))
        )

    def column_names_by_file(self, csv_dir: Path) -> dict[str, list[str]]:
        return {
            path.name: CsvHandler().read(path).columns
            for path in sorted(csv_dir.glob("*.csv"))
        }

    def to_dict(self, profiles: tuple[TableProfile, ...]) -> dict[str, object]:
        return {
            "tables": [
                {
                    "file": profile.file,
                    "rows": profile.rows,
                    "columns": list(profile.columns),
                    "column_profiles": [
                        {
                            "name": column.name,
                            "blank_count": column.blank_count,
                            "null_like_count": column.null_like_count,
                            "unique_count": column.unique_count,
                            "inferred_type": column.inferred_type,
                            "top_values": column.top_values,
                        }
                        for column in profile.column_profiles
                    ],
                }
                for profile in profiles
            ]
        }
