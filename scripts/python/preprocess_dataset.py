#!/usr/bin/env python3
"""Run WARNY-BI dataset preprocessing tasks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from warny_bi.eda import DatasetProfiler
from warny_bi.io import CsvHandler
from warny_bi.preprocess import DatasetPreprocessor
from warny_bi.validate import DatasetSchemaReporter, DatasetValidator


def default_raw_dir() -> Path:
    return PROJECT_ROOT / "data" / "raw"


def default_processed_dir() -> Path:
    return PROJECT_ROOT / "data" / "processed"


def default_image_dir() -> Path:
    return PROJECT_ROOT / "data" / "images"


def print_json(payload: dict[str, object]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def run_validate(args: argparse.Namespace) -> int:
    result = DatasetValidator(CsvHandler(), args.raw_dir, args.image_dir).run()
    print_json({"passed": result.passed, "errors": list(result.errors), "warnings": list(result.warnings)})
    return 0 if result.passed else 1


def run_eda(args: argparse.Namespace) -> int:
    csv_handler = CsvHandler()
    profiler = DatasetProfiler(csv_handler)
    profiles = profiler.profile_directory(args.raw_dir)
    payload = profiler.to_dict(profiles)
    if args.output_file:
        args.output_file.parent.mkdir(parents=True, exist_ok=True)
        args.output_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote EDA profile to {args.output_file}")
    else:
        print_json(payload)
    return 0


def run_clean(args: argparse.Namespace) -> int:
    result = DatasetPreprocessor(CsvHandler(), args.raw_dir, args.processed_dir, args.image_dir).run(args.schema_file)
    print_json(result)
    return 0


def run_schema(args: argparse.Namespace) -> int:
    csv_handler = CsvHandler()
    reporter = DatasetSchemaReporter(csv_handler)
    schema = reporter.build_schema(args.csv_dir)
    output_file = args.output_file or args.processed_dir / "schema.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(reporter.to_json(schema), encoding="utf-8")
    print(f"Wrote schema to {output_file}")
    return 0


def add_common_paths(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--raw-dir", type=Path, default=default_raw_dir())
    parser.add_argument("--processed-dir", type=Path, default=default_processed_dir())
    parser.add_argument("--image-dir", type=Path, default=default_image_dir())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WARNY-BI preprocessing CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate", help="Validate raw CSV and image inputs")
    add_common_paths(validate_parser)
    validate_parser.set_defaults(func=run_validate)

    eda_parser = subparsers.add_parser("eda", help="Profile raw CSV inputs")
    add_common_paths(eda_parser)
    eda_parser.add_argument("--output-file", type=Path, default=None)
    eda_parser.set_defaults(func=run_eda)

    clean_parser = subparsers.add_parser("clean", help="Write SQL-ready processed CSVs and schema.json")
    add_common_paths(clean_parser)
    clean_parser.add_argument("--schema-file", type=Path, default=None)
    clean_parser.set_defaults(func=run_clean)

    schema_parser = subparsers.add_parser("schema", help="Generate schema.json from a CSV directory")
    add_common_paths(schema_parser)
    schema_parser.add_argument("--csv-dir", type=Path, default=default_processed_dir())
    schema_parser.add_argument("--output-file", type=Path, default=None)
    schema_parser.set_defaults(func=run_schema)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
