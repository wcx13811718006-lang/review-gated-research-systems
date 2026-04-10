from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceRecord, ValidationResult
from ..utils.io import write_csv_rows, write_json, write_text


def _relative_to(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def write_demo_outputs(
    repo_root: Path,
    output_dir: Path,
    metadata: dict[str, Any],
    records: list[SourceRecord],
    validation_results: list[ValidationResult],
    review_packet: dict[str, Any],
    review_markdown: str,
) -> dict[str, str]:
    records_by_id = {record.record_id: record.to_dict() for record in records}

    routing_path = output_dir / "routing_decisions.json"
    review_json_path = output_dir / "review_packet.json"
    review_md_path = output_dir / "review_packet.md"
    final_export_path = output_dir / "final_export.json"
    status_table_path = output_dir / "system_status.csv"
    analysis_brief_path = output_dir / "analysis_brief.md"
    summary_path = output_dir / "run_summary.json"

    write_json(
        routing_path,
        {
            "project_id": metadata["project"]["project_id"],
            "decisions": [result.to_dict() for result in validation_results],
        },
    )
    write_json(review_json_path, review_packet)
    write_text(review_md_path, review_markdown)

    final_export = {
        "project": metadata["project"],
        "analysis_ready_records": [
            {
                "record": records_by_id[result.record_id],
                "decision": result.decision,
                "route_lane": result.route_lane,
            }
            for result in validation_results
            if not result.review_required
        ],
        "review_queue_records": [
            {
                "record": records_by_id[result.record_id],
                "decision": result.decision,
                "route_lane": result.route_lane,
                "decision_reason": result.decision_reason,
            }
            for result in validation_results
            if result.review_required
        ],
        "next_actions": [
            "repair or enrich records that failed readiness checks",
            "submit approved records to downstream analysis tasks",
        ],
    }
    write_json(final_export_path, final_export)

    status_rows = [
        {
            "record_id": result.record_id,
            "title": result.title,
            "source_type": result.source_type,
            "route_lane": result.route_lane,
            "decision": result.decision,
            "downstream_queue": result.downstream_queue,
            "decision_reason": result.decision_reason,
        }
        for result in validation_results
    ]
    write_csv_rows(
        status_table_path,
        fieldnames=[
            "record_id",
            "title",
            "source_type",
            "route_lane",
            "decision",
            "downstream_queue",
            "decision_reason",
        ],
        rows=status_rows,
    )

    analysis_brief = _render_analysis_brief(final_export)
    write_text(analysis_brief_path, analysis_brief)

    summary = {
        "project_name": metadata["project"]["project_name"],
        "records_processed": len(records),
        "approved_for_analysis": len(final_export["analysis_ready_records"]),
        "needs_human_review": len(final_export["review_queue_records"]),
        "artifact_manifest": {
            "routing_decisions": _relative_to(routing_path, repo_root),
            "review_packet_json": _relative_to(review_json_path, repo_root),
            "review_packet_markdown": _relative_to(review_md_path, repo_root),
            "final_export": _relative_to(final_export_path, repo_root),
            "system_status": _relative_to(status_table_path, repo_root),
            "analysis_brief": _relative_to(analysis_brief_path, repo_root),
        },
    }
    write_json(summary_path, summary)

    return {
        "routing_decisions": _relative_to(routing_path, repo_root),
        "review_packet_json": _relative_to(review_json_path, repo_root),
        "review_packet_markdown": _relative_to(review_md_path, repo_root),
        "final_export": _relative_to(final_export_path, repo_root),
        "system_status": _relative_to(status_table_path, repo_root),
        "analysis_brief": _relative_to(analysis_brief_path, repo_root),
        "run_summary": _relative_to(summary_path, repo_root),
    }


def _render_analysis_brief(final_export: dict[str, Any]) -> str:
    lines = [
        "# Analysis Brief",
        "",
        "This brief summarizes what is ready for downstream analysis and what remains gated for review.",
        "",
        "## Analysis-Ready Records",
        "",
    ]

    approved = final_export["analysis_ready_records"]
    if not approved:
        lines.append("- No records are currently approved for downstream analysis.")
    else:
        for item in approved:
            record = item["record"]
            tags = ", ".join(record["project_tags"])
            lines.extend(
                [
                    f"### {record['record_id']}: {record['title']}",
                    "",
                    f"- source_type: {record['source_type']}",
                    f"- route_lane: {item['route_lane']}",
                    f"- tags: {tags}",
                    f"- note: {record['notes']}",
                    "",
                ]
            )

    pending = final_export["review_queue_records"]
    lines.extend(["## Records Still Gated", ""])
    if not pending:
        lines.append("- No records are waiting for review.")
    else:
        for item in pending:
            record = item["record"]
            lines.extend(
                [
                    f"### {record['record_id']}: {record['title']}",
                    "",
                    f"- route_lane: {item['route_lane']}",
                    f"- hold_reason: {item['decision_reason']}",
                    "",
                ]
            )

    lines.extend(
        [
            "## Suggested Next Steps",
            "",
            "- use approved records for downstream note-building, coding, or analysis preparation",
            "- repair or enrich gated records before merging them into the analysis-ready set",
            "",
        ]
    )
    return "\n".join(lines)
