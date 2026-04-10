from __future__ import annotations

from ..models import SourceRecord


def route_record(record: SourceRecord) -> dict[str, str]:
    if record.source_type == "pdf":
        return {
            "route_lane": "pdf_ingest_lane",
            "next_stage": "validation_gate",
            "routing_reason": "Document-like artifact requires extraction-quality checks.",
        }

    return {
        "route_lane": "literature_ingest_lane",
        "next_stage": "validation_gate",
        "routing_reason": "Link-like artifact enters structured literature intake.",
    }


def route_records(records: list[SourceRecord]) -> dict[str, dict[str, str]]:
    return {record.record_id: route_record(record) for record in records}

