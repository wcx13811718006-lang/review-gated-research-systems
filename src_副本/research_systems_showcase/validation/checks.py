from __future__ import annotations

from ..models import SourceRecord, ValidationResult


def _abstract_word_count(record: SourceRecord) -> int:
    return len(record.abstract.split())


def _pdf_text_length(record: SourceRecord) -> int:
    return len(record.synthetic_text.strip())


def validate_records(
    records: list[SourceRecord],
    routed: dict[str, dict[str, str]],
    thresholds: dict[str, int],
) -> list[ValidationResult]:
    results: list[ValidationResult] = []

    for record in records:
        checks: list[dict[str, object]] = []

        checks.append(
            {
                "name": "required_fields_present",
                "passed": all([record.record_id, record.title, record.locator, record.notes]),
                "detail": "Record has the minimum required fields for intake.",
            }
        )

        if record.source_type == "link":
            year_present = bool(record.metadata.get("year"))
            abstract_words = _abstract_word_count(record)
            checks.extend(
                [
                    {
                        "name": "citation_year_present",
                        "passed": year_present,
                        "detail": "Link-like sources should include a year for downstream citation hygiene.",
                    },
                    {
                        "name": "abstract_length_threshold",
                        "passed": abstract_words >= thresholds["minimum_link_abstract_words"],
                        "detail": f"Abstract word count: {abstract_words}.",
                    },
                ]
            )
        else:
            text_length = _pdf_text_length(record)
            checks.extend(
                [
                    {
                        "name": "document_text_threshold",
                        "passed": text_length >= thresholds["minimum_pdf_text_characters"],
                        "detail": f"Extracted placeholder text length: {text_length}.",
                    },
                    {
                        "name": "ocr_suspected_flag",
                        "passed": not bool(record.metadata.get("ocr_suspected")),
                        "detail": "OCR suspicion keeps the record review-gated in this public demo.",
                    },
                ]
            )

        failed_checks = [check for check in checks if not check["passed"]]
        review_required = bool(failed_checks)

        if review_required:
            reason = "; ".join(str(check["name"]) for check in failed_checks)
            results.append(
                ValidationResult(
                    record_id=record.record_id,
                    title=record.title,
                    source_type=record.source_type,
                    route_lane=routed[record.record_id]["route_lane"],
                    decision="needs_human_review",
                    decision_reason=reason,
                    review_required=True,
                    checks=checks,
                    downstream_queue="review_queue",
                )
            )
            continue

        results.append(
            ValidationResult(
                record_id=record.record_id,
                title=record.title,
                source_type=record.source_type,
                route_lane=routed[record.record_id]["route_lane"],
                decision="approved_for_analysis",
                decision_reason="All demo validation checks passed.",
                review_required=False,
                checks=checks,
                downstream_queue="analysis_ready",
            )
        )

    return results

