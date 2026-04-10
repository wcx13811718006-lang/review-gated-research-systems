from __future__ import annotations

from typing import Any

from ..models import SourceRecord, ValidationResult


def build_review_packet(
    metadata: dict[str, Any],
    records: list[SourceRecord],
    validation_results: list[ValidationResult],
) -> dict[str, Any]:
    records_by_id = {record.record_id: record for record in records}
    review_items = []
    approved_items = []

    for result in validation_results:
        record = records_by_id[result.record_id]
        item = {
            "record_id": result.record_id,
            "title": result.title,
            "source_type": result.source_type,
            "route_lane": result.route_lane,
            "decision": result.decision,
            "decision_reason": result.decision_reason,
            "project_tags": record.project_tags,
            "notes": record.notes,
            "checks": result.checks,
        }
        if result.review_required:
            item["review_questions"] = [
                "Is the source description complete enough for downstream use?",
                "Should the record be revised, enriched, or held out of the analysis set?",
            ]
            review_items.append(item)
        else:
            approved_items.append(item)

    return {
        "packet_id": "demo_review_packet",
        "project": metadata["project"],
        "approved_records": approved_items,
        "review_queue_records": review_items,
        "human_action_checklist": [
            "Confirm whether incomplete metadata can be repaired.",
            "Confirm whether degraded document text should trigger a richer extraction step.",
            "Approve only the records that meet downstream readiness standards.",
        ],
    }


def render_review_packet_markdown(packet: dict[str, Any]) -> str:
    project = packet["project"]
    lines = [
        f"# Review Packet: {project['project_name']}",
        "",
        "## Purpose",
        "",
        "This packet highlights records that should pause for human review before downstream analysis.",
        "",
        "## Project Context",
        "",
        f"- project_id: {project['project_id']}",
        f"- research_question: {project['research_question']}",
        "",
        "## Records Approved For Analysis",
        "",
    ]

    if not packet["approved_records"]:
        lines.append("- None in this demo run.")
    else:
        for item in packet["approved_records"]:
            lines.extend(
                [
                    f"### {item['record_id']}: {item['title']}",
                    "",
                    f"- route_lane: {item['route_lane']}",
                    f"- decision: {item['decision']}",
                    f"- reason: {item['decision_reason']}",
                    "",
                ]
            )

    lines.extend(["## Records Requiring Review", ""])
    if not packet["review_queue_records"]:
        lines.append("- No review-gated items in this demo run.")
    else:
        for item in packet["review_queue_records"]:
            lines.extend(
                [
                    f"### {item['record_id']}: {item['title']}",
                    "",
                    f"- source_type: {item['source_type']}",
                    f"- route_lane: {item['route_lane']}",
                    f"- decision_reason: {item['decision_reason']}",
                    f"- notes: {item['notes']}",
                    "",
                    "Checks:",
                ]
            )
            for check in item["checks"]:
                status = "pass" if check["passed"] else "review"
                lines.append(f"- [{status}] {check['name']}: {check['detail']}")
            lines.extend(["", "Review questions:"])
            for question in item["review_questions"]:
                lines.append(f"- {question}")
            lines.append("")

    lines.extend(["## Human Action Checklist", ""])
    for step in packet["human_action_checklist"]:
        lines.append(f"- {step}")

    lines.append("")
    return "\n".join(lines)

