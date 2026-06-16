"""Processed CSV to SQL Server loading workflow."""

from __future__ import annotations

import argparse

from warnybi.config import EnvSettings
from warnybi.sql import SqlClient


class DatabaseLoadCli:
    """CLI for processed CSVs to SQL Server."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Load processed WARNY-BI CSV files into SQL Server")
        parser.add_argument("--append", action="store_true", help="Append rows instead of replacing destination tables")
        args = parser.parse_args()

        settings = EnvSettings().load()
        results = SqlClient(settings.sql).load_processed_csvs(
            settings.processed_dir,
            settings.sql_load_batch_size,
            args.append,
        )
        for result in results:
            print(f"{result.table_name}: loaded {result.rows_loaded} rows from {result.csv_path}")
        return 0
