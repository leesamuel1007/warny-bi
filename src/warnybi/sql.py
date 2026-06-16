"""SQL Server operations for WARNY-BI."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import pyodbc

from warnybi.config import SqlSettings
from warnybi.models import LoadResult, RagDocument, RagResponse


@dataclass(frozen=True)
class TableLoadSpec:
    table_name: str
    csv_name: str


class SqlClient:
    """Owns WARNY-BI SQL Server reads, writes, and processed CSV loads."""

    LOAD_ORDER = (
        TableLoadSpec("dataset_sources", "dataset_sources.csv"),
        TableLoadSpec("warning_light_catalog", "warning_light_catalog.csv"),
        TableLoadSpec("maintenance_service_map", "maintenance_service_map.csv"),
        TableLoadSpec("recall_data", "recall_data.csv"),
        TableLoadSpec("scenario_validation", "scenario_validation.csv"),
        TableLoadSpec("warning_light_image_catalog", "warning_light_image_catalog.csv"),
    )

    def __init__(self, settings: SqlSettings) -> None:
        self.settings = settings

    def connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self.settings.odbc_connection_string())

    def load_processed_csvs(self, processed_dir: Path, batch_size: int, append: bool) -> list[LoadResult]:
        if not processed_dir.is_dir():
            raise FileNotFoundError(f"Processed CSV directory not found: {processed_dir}")
        if batch_size < 1:
            raise ValueError("batch_size must be at least 1")

        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.fast_executemany = True
            if not append:
                for spec in reversed(self.LOAD_ORDER):
                    cursor.execute(f"DELETE FROM dbo.{spec.table_name}")
            results = [self.load_table(cursor, processed_dir, spec, batch_size) for spec in self.LOAD_ORDER]
            connection.commit()
        return results

    def load_table(self, cursor: Any, processed_dir: Path, spec: TableLoadSpec, batch_size: int) -> LoadResult:
        csv_path = processed_dir / spec.csv_name
        if not csv_path.is_file():
            raise FileNotFoundError(f"Processed CSV file not found: {csv_path}")
        columns, rows = self.read_csv(csv_path)
        if rows:
            column_sql = ", ".join(f"[{column}]" for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            insert_sql = f"INSERT INTO dbo.{spec.table_name} ({column_sql}) VALUES ({placeholders})"
            for index in range(0, len(rows), batch_size):
                cursor.executemany(insert_sql, rows[index : index + batch_size])
        return LoadResult(spec.table_name, str(csv_path), len(rows))

    def read_csv(self, csv_path: Path) -> tuple[list[str], list[tuple[str | None, ...]]]:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError(f"CSV has no header: {csv_path}")
            columns = list(reader.fieldnames)
            rows = [tuple(self.clean_value(row[column]) for column in columns) for row in reader]
        return columns, rows

    def clean_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None

    def read_documents(self, view_name: str) -> list[RagDocument]:
        query = f"""
            SELECT document_id, source_type, source_id, warning_light_id,
                   warning_light_name, make, model, model_year,
                   component_category, severity, recommended_service_type,
                   content, source_url, image_path, review_status
            FROM {view_name}
            ORDER BY document_id
        """
        with self.connect() as connection:
            cursor = connection.cursor()
            rows = cursor.execute(query).fetchall()
            columns = [column[0] for column in cursor.description]
        return [self.row_to_document(dict(zip(columns, row, strict=True))) for row in rows]

    def row_to_document(self, row: dict[str, Any]) -> RagDocument:
        return RagDocument(
            document_id=row["document_id"],
            source_type=row["source_type"],
            source_id=row["source_id"],
            warning_light_id=row["warning_light_id"],
            warning_light_name=row["warning_light_name"],
            make=row["make"],
            model=row["model"],
            model_year=row["model_year"],
            component_category=row["component_category"],
            severity=row["severity"],
            recommended_service_type=row["recommended_service_type"],
            content=row["content"] or "",
            source_url=row["source_url"],
            image_path=row["image_path"],
            review_status=row["review_status"],
        )

    def insert_query_log(self, response: RagResponse, pipeline: str) -> None:
        answer_json = json.dumps(response.answer.to_dict(), ensure_ascii=False, separators=(",", ":"))
        citations_json = json.dumps(
            [self.evidence_log_payload(item) for item in response.evidence],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        upstream_response_json = json.dumps(response.to_dict(), ensure_ascii=False, separators=(",", ":"))
        with self.connect() as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO dbo.query_log (
                    query_id,
                    created_at_utc,
                    pipeline,
                    user_prompt,
                    top_k,
                    include_image_evidence,
                    answer_json,
                    citations_json,
                    azure_response_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                str(uuid4()),
                datetime.now(timezone.utc).replace(tzinfo=None),
                pipeline,
                response.query,
                response.top_k,
                response.include_image_evidence,
                answer_json,
                citations_json,
                upstream_response_json,
            )
            connection.commit()

    def evidence_log_payload(self, evidence: Any) -> dict[str, Any]:
        payload = evidence.to_dict()
        payload["content"] = evidence.content
        return payload
