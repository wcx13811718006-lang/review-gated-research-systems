# Review Packet: Digital Economy Literature Intake Demo

## Purpose

This packet highlights records that should pause for human review before downstream analysis.

## Project Context

- project_id: demo_digital_economy_review_gate
- research_question: How can a review-gated research system support structured intake before downstream analysis?

## Records Approved For Analysis

### link_platform_adoption: Digital platform adoption note

- route_lane: literature_ingest_lane
- decision: approved_for_analysis
- reason: All demo validation checks passed.

## Records Requiring Review

### link_firm_dynamics: Firm dynamics working paper

- source_type: link
- route_lane: literature_ingest_lane
- decision_reason: citation_year_present
- notes: Useful lead, but metadata is incomplete and should be reviewed before downstream use.

Checks:
- [pass] required_fields_present: Record has the minimum required fields for intake.
- [review] citation_year_present: Link-like sources should include a year for downstream citation hygiene.
- [pass] abstract_length_threshold: Abstract word count: 15.

Review questions:
- Is the source description complete enough for downstream use?
- Should the record be revised, enriched, or held out of the analysis set?

### pdf_policy_appendix: Policy appendix placeholder

- source_type: pdf
- route_lane: pdf_ingest_lane
- decision_reason: ocr_suspected_flag
- notes: Placeholder artifact used to demonstrate degraded extraction and review routing.

Checks:
- [pass] required_fields_present: Record has the minimum required fields for intake.
- [pass] document_text_threshold: Extracted placeholder text length: 231.
- [review] ocr_suspected_flag: OCR suspicion keeps the record review-gated in this public demo.

Review questions:
- Is the source description complete enough for downstream use?
- Should the record be revised, enriched, or held out of the analysis set?

## Human Action Checklist

- Confirm whether incomplete metadata can be repaired.
- Confirm whether degraded document text should trigger a richer extraction step.
- Approve only the records that meet downstream readiness standards.
