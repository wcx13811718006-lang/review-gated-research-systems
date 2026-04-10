# Review Logic

This document explains the public demo's gating behavior in plain language.

## Decision Pattern

1. A record enters the system with basic metadata and a locator.
2. The routing layer assigns it to a source-appropriate lane.
3. The validation layer checks whether the record is safe to move downstream.
4. If the checks pass, the record is marked analysis-ready.
5. If the checks fail, the record is routed into a structured review packet.

## Demo Rules

| Rule | Pass condition | Review trigger |
| --- | --- | --- |
| `required_fields_present` | minimum intake fields are present | missing essential intake fields |
| `citation_year_present` | link-like source has a year | incomplete citation metadata |
| `abstract_length_threshold` | abstract is long enough for a first-pass summary | abstract is too short to support confidence |
| `document_text_threshold` | document text is long enough to inspect | document text is too weak or incomplete |
| `ocr_suspected_flag` | no OCR concern is present | extraction quality looks degraded |

## Why This Matters

- The system makes uncertainty legible.
- Weak records are paused early instead of becoming downstream cleanup problems.
- Human review becomes part of the architecture rather than an ad hoc afterthought.
- The handoff artifacts are easier to explain in academic settings because each decision leaves a visible trace.
