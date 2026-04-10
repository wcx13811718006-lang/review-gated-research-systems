from __future__ import annotations

from pathlib import Path

from .export.writer import write_demo_outputs
from .ingest.loader import load_demo_inputs
from .review.packets import build_review_packet, render_review_packet_markdown
from .routing.router import route_records
from .utils.io import ensure_directory, write_json
from .utils.progress import append_progress_event
from .validation.checks import validate_records


def run_demo_pipeline(input_dir: Path, output_dir: Path) -> dict[str, object]:
    repo_root = input_dir.parents[1]
    ensure_directory(output_dir)

    progress_path = output_dir / "progress_log.jsonl"
    if progress_path.exists():
        progress_path.unlink()

    metadata, records = load_demo_inputs(input_dir)
    append_progress_event(progress_path, "ingest", "Loaded demo inputs.", len(records))

    routed = route_records(records)
    append_progress_event(progress_path, "route", "Assigned records to workflow lanes.", len(routed))

    validation_results = validate_records(records, routed, metadata["validation"])
    append_progress_event(
        progress_path,
        "validate",
        "Applied review-gate checks.",
        len(validation_results),
    )

    review_packet = build_review_packet(metadata, records, validation_results)
    review_markdown = render_review_packet_markdown(review_packet)
    append_progress_event(
        progress_path,
        "review_packet",
        "Prepared structured review packet.",
        len(review_packet["review_queue_records"]),
    )

    artifact_manifest = write_demo_outputs(
        repo_root=repo_root,
        output_dir=output_dir,
        metadata=metadata,
        records=records,
        validation_results=validation_results,
        review_packet=review_packet,
        review_markdown=review_markdown,
    )
    append_progress_event(progress_path, "export", "Wrote public demo artifacts.")

    try:
        progress_log_path = str(progress_path.relative_to(repo_root))
    except ValueError:
        progress_log_path = str(progress_path)

    manifest = {
        "summary": {
            "records_processed": len(records),
            "approved_for_analysis": sum(not result.review_required for result in validation_results),
            "needs_human_review": sum(result.review_required for result in validation_results),
        },
        "artifact_manifest": {
            **artifact_manifest,
            "progress_log": progress_log_path,
        },
    }
    write_json(output_dir / "manifest.json", manifest)
    return manifest
