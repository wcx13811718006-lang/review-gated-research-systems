# Local Validation Protocol

Every design round should end with local validation against existing research materials or historically reviewed records.

## Why This Exists

The goal is to reduce manual review cost while increasing verifiability. The system should not rely only on toy examples or model confidence. It should be replayed against materials that already have trusted human-reviewed outputs when those materials are available locally.

## Round-End Checklist

1. Run the public demo and tests.
2. Run local backend status checks.
3. Run at least one local source-material smoke test.
4. If historical coded data exists, run replay comparison against it.
5. Report what passed, what failed, and what changed in the design.
6. Keep private source files and private results out of the public repository.

## Historical Replay

For CCLD-style coding batches, keep a benchmark CSV outside the public repo with columns such as:

- `benchmark_FinalDecision`
- `benchmark_PartySource`
- `benchmark_Plaintiff`
- `benchmark_Plaintiff Type`
- `benchmark_Defendant`
- `benchmark_Defendant Type`
- `benchmark_Addressed Issue`
- `benchmark_Notes`
- `benchmark_QC_Flag`

Candidate model outputs can be stored with a different prefix, for example:

- `review_machine_FinalDecision`
- `new_ai_FinalDecision`

Then compare them locally:

```bash
research-ai-replay \
  --csv "/path/to/private/benchmark.csv" \
  --candidate-prefix review_machine_ \
  --output /tmp/research_ai_replay_report.json
```

The report is a triage artifact. Exact string match helps identify where review effort can be reduced, but it is not a substitute for legal or research judgment.

## Reading Results

- Fields with no mismatches are candidates for lighter review.
- Fields with mismatches should remain in normal review.
- Empty candidate fields indicate pipeline failure, not model uncertainty alone.
- Notes and free-text fields may need semantic review even when exact string match is low.
- Source previews in local run artifacts should be checked to confirm the model actually received usable text.
- PDF sources that cannot be extracted by the local optional extractor should be reported as extraction gaps, not scored as model failures.

## Required Reporting After Each Round

Each round should report:

- local files used for validation
- backend status
- model generation status
- source ingestion status
- replay comparison summary, if available
- failures found
- changes made to address those failures
- remaining limitations

## Design Adjustment Loop

When validation finds a failure, handle it in this order:

1. Identify whether the failure is source ingestion, model generation, schema mapping, comparison logic, or review routing.
2. Fix the earliest failing stage first.
3. Rerun the same local validation material.
4. Record whether the failure moved downstream, disappeared, or changed shape.
5. Keep unresolved cases review-gated.
