# Social Science Workflow Layer

This layer turns the local assistant from a single-project tool into a more general review-gated research workflow helper.

The design target is not full automation. The target is to make reading, extraction, verification, escalation, and human review more explicit across common social-science materials.

## Workflow Templates

Available templates:

- `paper`: academic papers
- `policy`: policy reports
- `legal`: legal or administrative documents
- `interview`: interview transcripts
- `web`: web-based sources

Show a template:

```bash
research-ai-local --config local_ai.config.json workflow --template paper
```

Write template artifacts:

```bash
research-ai-local --config local_ai.config.json workflow --template paper --project-name "pilot" --write
```

Each template defines:

- structured fields
- high-stakes fields
- validation checks
- stage-gated processing steps
- human-review boundaries

## Verification Audit

Run a deterministic audit over recent local AI artifacts:

```bash
research-ai-local --config local_ai.config.json audit --template paper
```

The audit checks recent runs for:

- review-required status
- non-exportable outputs
- generation failures
- fallback use
- missing included sources
- failed review-gate checks
- template-specific high-stakes review needs

The audit can recommend repair, rerun, escalation, or human review. It cannot approve final use.

## Review Memory

Record a human correction or codebook decision:

```bash
research-ai-local --config local_ai.config.json review-memory \
  --add \
  --run-id local_ai_1 \
  --field identification_strategy \
  --decision revise \
  --correction "The design is descriptive, not causal." \
  --rationale "No comparison group or timing design was shown."
```

Summarize local review memory:

```bash
research-ai-local --config local_ai.config.json review-memory
```

Review memory is stored locally as JSONL and summary artifacts. It is a retrieval and calibration layer, not automatic approval and not model fine-tuning.

## Intended Pilot Use

A small pilot can use this sequence:

1. `acquire`: collect explicit files or URLs into traceable artifacts.
2. `workflow`: choose the correct material template.
3. `ask` or `ideate`: generate draft extraction or research starting points.
4. `audit`: detect batch-level risks and recurring error patterns.
5. `review-memory --add`: record human corrections and codebook decisions.
6. `memory`: inspect accumulated run artifacts.

Final claims remain the responsibility of the researcher.
