from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceRecord
from ..utils.io import load_json, read_csv_rows


def _split_tags(raw_tags: str) -> list[str]:
    return [tag.strip() for tag in raw_tags.split(";") if tag.strip()]


def load_demo_inputs(input_dir: Path) -> tuple[dict[str, Any], list[SourceRecord]]:
    metadata = load_json(input_dir / "sample_metadata.json")
    link_rows = read_csv_rows(input_dir / "sample_links.csv")
    pdf_text = (input_dir / "sample_pdf_placeholder.txt").read_text(encoding="utf-8")

    records: list[SourceRecord] = []

    for row in link_rows:
        records.append(
            SourceRecord(
                record_id=row["record_id"],
                source_type="link",
                title=row["title"],
                locator=row["url"],
                abstract=row["abstract"],
                project_tags=_split_tags(row["project_tags"]),
                notes=row["notes"],
                metadata={"year": row["year"]},
            )
        )

    pdf_record = metadata["pdf_record"]
    records.append(
        SourceRecord(
            record_id=pdf_record["record_id"],
            source_type=pdf_record["source_type"],
            title=pdf_record["title"],
            locator=pdf_record["locator"],
            abstract="Synthetic placeholder for a non-distributed document artifact.",
            project_tags=pdf_record["project_tags"],
            notes=pdf_record["notes"],
            metadata=pdf_record["metadata"],
            synthetic_text=pdf_text,
        )
    )

    return metadata, records

