"""CSV input and output containers for WARNY-BI."""

from __future__ import annotations

import csv
from pathlib import Path


class CsvHandler:
    """Reads, stores, modifies, and writes one CSV table."""

    def __init__(self, path: Path | None = None, encoding: str = "utf-8-sig") -> None:
        self.path = path
        self.encoding = encoding
        self.rows: list[dict[str, str]] = []
        self.columns: list[str] = []

    def read(self, path: Path | None = None) -> "CsvHandler":
        if path:
            self.path = path
        if not self.path:
            raise ValueError("CSV path is required before reading")

        with self.path.open("r", encoding=self.encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            self.columns = list(reader.fieldnames or [])
            self.rows = [dict(row) for row in reader]
        return self

    def write(self, path: Path | None = None, columns: list[str] | None = None) -> "CsvHandler":
        output_path = path or self.path
        if not output_path:
            raise ValueError("CSV path is required before writing")

        fieldnames = columns or self.columns
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(self.rows)
        self.path = output_path
        self.columns = list(fieldnames)
        return self

    def set_rows(self, rows: list[dict[str, str]], columns: list[str] | None = None) -> "CsvHandler":
        self.rows = rows
        self.columns = columns or self.infer_columns(rows)
        return self

    def reorder_columns(self, columns: list[str]) -> "CsvHandler":
        self.columns = columns
        return self

    def infer_columns(self, rows: list[dict[str, str]]) -> list[str]:
        if not rows:
            return []
        return list(rows[0].keys())
