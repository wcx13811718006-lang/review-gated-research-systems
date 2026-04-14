# Case Study

This note gives a sanitized example of how a review-gated research system handles records with different evidence-quality profiles. The contribution is not that AI replaces researchers. The contribution is that AI can help organize intake, structure uncertainty, and produce better handoff artifacts before downstream use.

## Three Public Demo Cases

The public demo centers on three simple cases:

1. a valid case that can move forward safely
2. an ambiguous case that should pause for review
3. a degraded case that should remain visible but should not move downstream

## Example Handling

| Case | Initial condition | Routing outcome | Gate decision | Human role | Downstream result |
| --- | --- | --- | --- | --- | --- |
| Valid case | metadata is complete and the source is readable enough for first-pass use | routed to the standard lane | pass | optional spot check | analysis-ready export |
| Ambiguous case | source may be useful, but metadata is incomplete or context is weak | routed to review | review | inspect, enrich, revise, or hold | structured review packet; no downstream use until cleared |
| Degraded case | extraction quality is weak, provenance is incomplete, or the artifact is not fit for confident reuse | routed away from automatic pass-through | hold or review | decide whether to repair, replace, or exclude | preserved as an inspectable failure or review artifact |

## Why The Distinction Matters

In research settings, the difference between “usable,” “ambiguous,” and “degraded” should be explicit. A system that silently passes along uncertain records creates verification debt later. A review-gated design reduces that risk by separating what is ready for downstream use from what still needs judgment.

## Public Demo Alignment

The public demo illustrates these cases in compact form:

- a link-like record with sufficient metadata is exported as analysis-ready
- a link-like record with missing citation detail is routed into review
- a document placeholder with degraded text quality is routed into review rather than treated as analysis-ready evidence

## What The Reader Should Notice

- the system preserves the ambiguous and degraded cases rather than hiding them
- the review artifact explains why the record was paused
- the export contains only the record that clears the gate
- the architecture rewards caution over apparent throughput

## What This Case Study Does Not Claim

This case study does not claim comprehensive document handling, autonomous literature review, or full substitution for human research judgment. It demonstrates a design pattern for responsible AI-assisted research operations.
