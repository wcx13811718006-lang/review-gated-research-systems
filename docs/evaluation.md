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

