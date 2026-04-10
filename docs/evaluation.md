# Evaluation

This repository does not frame evaluation around automation rate. A more relevant question for research-support systems is whether the system separates records appropriately into pass, review, and hold states before downstream use.

## Evaluation Focus

The central evaluation question is:

How well does the system support downstream safety by distinguishing records that are ready for use from records that still require human judgment?

## What Matters Most

### Decision quality

The system should avoid treating any generated or extracted output as trustworthy merely because it exists. A stronger result is one in which:

- clearly usable records move forward
- uncertain records pause for review
- unsuitable records are held back

### Downstream safety

Evaluation should consider whether later research work begins from evidence that has passed appropriate checks. In practice, this means the system should reduce silent propagation of weak metadata, degraded document extraction, or unsupported summaries.

### Review usefulness

When a record is routed to review, the resulting packet should help a human reviewer understand why the record was paused and what action is needed next.


## Current Evaluation Gaps

The current public evaluation framing is directionally strong, but several gaps still make it hard to judge quality rigorously:

1. **No explicit scorecard or thresholds**
   The document describes what matters but does not define measurable targets (for example, acceptable false-pass rate or maximum unresolved-review backlog).

2. **No error taxonomy**
   Failure modes (metadata gaps, extraction degradation, citation issues) are mentioned, but they are not grouped into a formal taxonomy that supports consistent analysis over time.

3. **No baseline comparison**
   There is no side-by-side comparison against an ungated workflow or alternate routing strategy, so it is hard to quantify the value added by review gating.

4. **No reviewer agreement signal**
   The framework does not yet include inter-reviewer consistency checks, which are important when human judgment is a core safety mechanism.

5. **No longitudinal drift checks**
   The evaluation view is static and does not define how to monitor quality drift across batches, source domains, or extraction-tool changes.

6. **No queue-health and latency metrics**
   Review usefulness is discussed, but practical operations metrics (time-to-review, stale packet rate, rework frequency) are missing.

7. **No calibration loop back into rules**
   The document does not specify how reviewer outcomes should feed back into threshold tuning, rule updates, and release gating.

## Suggested Next-Step Metrics

A lightweight public-safe scorecard could include:

- **Safety metrics:** false-pass rate, hold precision, critical-miss count
- **Workflow metrics:** review queue size, median review latency, reopen rate
- **Quality metrics:** citation completeness, extraction integrity score, packet actionability rating
- **Stability metrics:** metric drift by source type and by run date

These additions would keep the conservative philosophy intact while making evaluation more auditable and reproducible.

## What This Repository Does Not Claim

- it does not claim benchmark leadership
- it does not claim comprehensive coverage of all document or source types
- it does not claim that automated pass-through is the primary success metric
- it does not claim to replace human research judgment

## Reasonable Public Demonstration Criteria

For a public showcase like this one, a sensible standard is whether the demo makes the following visible:

- the difference between accepted, review-gated, and held records
- the reason each decision was made
- the outputs that are safe to pass downstream
- the points where human oversight remains necessary

## Research-Oriented Interpretation

In academic settings, a conservative system may be preferable to an aggressive one. A higher review rate is not automatically a weakness if it prevents questionable material from entering later analysis without scrutiny. For that reason, this repository emphasizes decision quality, review routing, and downstream-safe outputs rather than raw automation volume.

