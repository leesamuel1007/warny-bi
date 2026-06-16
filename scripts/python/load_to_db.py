#!/usr/bin/env python3
"""Load processed WARNY-BI CSV files into SQL Server through ODBC."""

from warnybi.workflows.load_db import DatabaseLoadCli


if __name__ == "__main__":
    raise SystemExit(DatabaseLoadCli().run())
