from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json


def _normalize_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text)
    return text.strip().casefold()


def _display_cell(value: Any, limit: int = 240) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _field_names(rows: list[dict[str, str]], reference_prefix: str, candidate_prefix: str) -> list[str]:
    if not rows:
        return []
    columns = set(rows[0].keys())
    reference_fields = {
        column[len(reference_prefix) :]
        for column in columns
        if column.startswith(reference_prefix)
    }
    candidate_fields = {
        column[len(candidate_prefix) :]
        for column in columns
        if column.startswith(candidate_prefix)
    }
    return sorted(reference_fields & candidate_fields)


def compare_prefixed_columns(
    csv_path: Path,
    output_path: Path,
    reference_prefix: str = "benchmark_",
    candidate_prefix: str = "review_machine_",
    id_column: str = "row_id",
) -> dict[str, Any]:
    rows = _read_csv(csv_path)
    fields = _field_names(rows, reference_prefix, candidate_prefix)
    field_summary: dict[str, dict[str, Any]] = {}
    mismatches: list[dict[str, Any]] = []

    for field in fields:
        compared = 0
        matches = 0
        blanks = 0
        candidate_blank_mismatches = 0
        for index, row in enumerate(rows, start=1):
            reference = row.get(reference_prefix + field, "")
            candidate = row.get(candidate_prefix + field, "")
            if not _normalize_cell(reference) and not _normalize_cell(candidate):
                blanks += 1
                continue
            compared += 1
            matched = _normalize_cell(reference) == _normalize_cell(candidate)
            if matched:
                matches += 1
            else:
                if _normalize_cell(reference) and not _normalize_cell(candidate):
                    candidate_blank_mismatches += 1
                mismatches.append(
                    {
                        "row_number": index,
                        "row_id": row.get(id_column, ""),
                        "field": field,
                        "reference": _display_cell(reference),
                        "candidate": _display_cell(candidate),
                    }
                )

        field_summary[field] = {
            "compared": compared,
            "matches": matches,
            "mismatches": compared - matches,
            "blank_pairs_skipped": blanks,
            "candidate_blank_mismatches": candidate_blank_mismatches,
            "exact_match_rate": round(matches / compared, 4) if compared else None,
        }

    total_compared = sum(item["compared"] for item in field_summary.values())
    total_matches = sum(item["matches"] for item in field_summary.values())
    result = {
        "source_csv": str(csv_path),
        "reference_prefix": reference_prefix,
        "candidate_prefix": candidate_prefix,
        "row_count": len(rows),
        "field_count": len(fields),
        "total_compared_cells": total_compared,
        "total_matches": total_matches,
        "total_mismatches": total_compared - total_matches,
        "overall_exact_match_rate": round(total_matches / total_compared, 4) if total_compared else None,
        "field_summary": field_summary,
        "mismatches": mismatches,
        "review_cost_signal": {
            "fields_with_no_mismatches": [
                field for field, summary in field_summary.items() if summary["mismatches"] == 0 and summary["compared"]
            ],
            "fields_requiring_review": [
                field for field, summary in field_summary.items() if summary["mismatches"] > 0
            ],
            "fields_with_empty_candidate_outputs": [
                field for field, summary in field_summary.items() if summary["candidate_blank_mismatches"] > 0
            ],
            "note": "Use this as a triage signal only. Exact string match is not a substitute for legal review.",
        },
    }

    ensure_directory(output_path.parent)
    write_json(output_path, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare historical reference coding with candidate AI output.")
    parser.add_argument("--csv", required=True, type=Path, help="CSV containing reference and candidate prefixed columns.")
    parser.add_argument("--output", required=True, type=Path, help="Path to write JSON comparison report.")
    parser.add_argument("--reference-prefix", default="benchmark_")
    parser.add_argument("--candidate-prefix", default="review_machine_")
    parser.add_argument("--id-column", default="row_id")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = compare_prefixed_columns(
        csv_path=args.csv,
        output_path=args.output,
        reference_prefix=args.reference_prefix,
        candidate_prefix=args.candidate_prefix,
        id_column=args.id_column,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
