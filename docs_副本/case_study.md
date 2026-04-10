# Case Study

This note gives a sanitized example of how a review-gated research system handles records with different evidence quality profiles. The goal is not to maximize automation. The goal is to separate records that are ready for downstream use from records that require review or should be held back.

## Scenario

Assume a small intake batch for a literature-support task contains three records:

1. a well-formed research note with complete citation metadata
2. a document-like artifact with incomplete or degraded extraction
3. a source with missing provenance and weak evidentiary value

## Example Handling

| Input type | Initial condition | Routing outcome | Gate decision | Human role | Downstream result |
| --- | --- | --- | --- | --- | --- |
| Valid input | metadata is complete, extraction is readable, source context is clear | routed to the standard literature lane | pass | optional spot check | analysis-ready export |
| Ambiguous input | source may be relevant, but metadata is incomplete or extraction quality is uncertain | routed to a review lane | review | inspect the record, repair metadata, or request a better source copy | structured review packet; no downstream use until cleared |
| Invalid input | provenance is weak, text is unusable, or the source does not meet minimum intake requirements | routed away from analysis | hold | decide whether to replace, exclude, or archive the record | held out of downstream use |

## What Changes Across The Three Cases

### 1. Valid input

A valid record is not merely one that can be parsed. It is one that has enough provenance and readable content to support later research work. In the public demo, this means the record can be exported as analysis-ready without bypassing the validation layer.

### 2. Ambiguous input

An ambiguous record may still be useful, but it is not yet safe for downstream use. A review-gated system treats this as a normal state. The record receives a structured review packet so a human can inspect what is known, what is missing, and what should happen next.

### 3. Invalid input

An invalid record should not be allowed to create false confidence downstream. If provenance is too weak, extraction fails badly, or the source is not fit for the task, the appropriate outcome is to hold or exclude it rather than force it through the system.

## Why This Matters

The distinction between pass, review, and hold is especially important in research settings. A weak source that quietly enters later analysis can create avoidable verification debt. A review-gated design makes those boundaries visible and supports more careful reuse of machine-assisted outputs.

## Public Demo Alignment

The public demo in this repository illustrates these patterns in simplified form:

- one record is cleared for downstream use
- one record is sent to review because metadata is incomplete
- one record is sent to review because document quality is uncertain

The examples are intentionally small and sanitized, but the logic reflects a broader research-systems concern: downstream work should begin only after evidence quality has been checked.

