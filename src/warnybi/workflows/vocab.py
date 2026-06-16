"""Canonical vocabulary generation for FOSS intent parsing."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from warnybi.config import EnvSettings


class CanonicalVocabBuilder:
    """Builds linked source vocabulary supplied to the intent parser."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.data_dir = root / "data" / "processed"

    def build(self) -> dict[str, list[dict[str, object]]]:
        light_rows = self._read_rows("warning_light_catalog.csv")
        recall_rows = self._read_rows("recall_data.csv")
        scenario_rows = self._read_rows("scenario_validation.csv")

        return {
            "warning_lights": self._warning_lights(light_rows),
            "vehicles": self._vehicles(recall_rows, scenario_rows),
        }

    def _warning_lights(self, light_rows: list[dict[str, str]]) -> list[dict[str, object]]:
        records: list[dict[str, object]] = []
        for row in light_rows:
            warning_light_id = row.get("warning_light_id", "")
            if not warning_light_id:
                continue
            records.append(
                {
                    "warning_light": row.get("warning_light_name", ""),
                    "warning_light_id": warning_light_id,
                    "component_category": row.get("component_category", ""),
                }
            )
        return sorted(records, key=lambda item: str(item["warning_light_id"]))

    def _vehicles(
        self,
        recall_rows: list[dict[str, str]],
        scenario_rows: list[dict[str, str]],
    ) -> list[dict[str, object]]:
        vehicles: dict[tuple[str, str, str], dict[str, object]] = {}
        for row in recall_rows + scenario_rows:
            make = row.get("make", "")
            model = row.get("model", "")
            model_year = row.get("model_year", "")
            if not (make or model or model_year):
                continue
            vehicles[(make, model, model_year)] = {
                "make": make or None,
                "model": model or None,
                "model_year": self._model_year(model_year),
            }
        return sorted(
            vehicles.values(),
            key=lambda item: (
                str(item["make"] or ""),
                str(item["model"] or ""),
                str(item["model_year"] or ""),
            ),
        )

    def _read_rows(self, csv_name: str) -> list[dict[str, str]]:
        path = self.data_dir / csv_name
        if not path.is_file():
            return []
        with path.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            return [{key: (value or "").strip() for key, value in row.items()} for row in reader]

    def _model_year(self, value: str) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


class BuildCanonicalVocabCli:
    """CLI for generating config/canonical_vocab.json."""

    def run(self) -> int:
        parser = argparse.ArgumentParser(description="Build the WARNY-BI canonical intent vocabulary")
        parser.add_argument(
            "--output",
            type=Path,
            default=None,
            help="Output JSON path. Defaults to config/canonical_vocab.json.",
        )
        args = parser.parse_args()

        root = EnvSettings().root
        output_path = args.output or (root / "config" / "canonical_vocab.json")
        payload = CanonicalVocabBuilder(root).build()
        output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {output_path}")
        return 0
