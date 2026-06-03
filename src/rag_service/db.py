"""SQL Server access classes for WARNY-BI RAG services."""

from __future__ import annotations

from typing import Any

import pyodbc

from rag_service.config import SqlConfig
from rag_service.documents import RagDocument


class SqlConnectionFactory:
    """Creates SQL Server connections from typed configuration."""

    def __init__(self, config: SqlConfig) -> None:
        self.config = config

    def connect(self) -> pyodbc.Connection:
        return pyodbc.connect(self.config.connection_string())


class SqlDocumentReader:
    """Reads RAG documents from a SQL view."""

    def __init__(self, connection_factory: SqlConnectionFactory, view_name: str) -> None:
        self.connection_factory = connection_factory
        self.view_name = view_name

    def read_documents(self) -> list[RagDocument]:
        query = f"""
            SELECT
                document_id,
                source_type,
                source_id,
                warning_light_id,
                warning_light_name,
                make,
                model,
                model_year,
                component_category,
                severity,
                recommended_service_type,
                content,
                source_url,
                image_path,
                review_status
            FROM {self.view_name}
            ORDER BY document_id
        """
        with self.connection_factory.connect() as connection:
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
