# Review-Gated Model Architecture

This repository uses a conservative local architecture rather than a fully autonomous research agent. The goal is to make model routing, review gates, and run artifacts easy to inspect.

## What Was Borrowed From Open-Source Agent Systems

The implementation borrows patterns, not stacks:

- LangGraph: explicit state transitions, durable execution thinking, and human inspection points.
- AutoGen and CrewAI: role separation between generation, review, and coordination.
- OpenHands: visible execution state, logs, and artifact paths.
- Hermes and OpenClaw: local-first model/provider visibility and user-facing operations surfaces.
- DeepScientist: findings memory, failed-branch preservation, and long-horizon research workflow discipline.

These patterns are kept inside a stricter review-gated local workflow. No external framework is required for this layer.

## Current Local Execution Plan

The local planner exposes these stages:

1. `source_intake`: read only user-selected source files and record source metadata.
2. `draft_generation`: use the configured primary backend for draft generation.
3. `review_backend_check`: use the configured review/fallback backend only when policy allows it.
4. `quality_gate`: run deterministic checks and block unreviewed final use.
5. `artifact_memory`: write request, draft, review gate, manifest, and failure context.
6. `human_review`: require human approval before downstream use.

The planner is available from the terminal:

```bash
research-ai-local --config local_ai.config.json architecture
```

It is also available from the local console through the `模型架构` command.

## Run Memory

The next layer is a read-only run-memory summary. It scans stored artifacts and reports:

- recent run IDs
- prompt or focus text
- backend and effective model
- fallback use
- review-gate decision
- failed checks
- generation failures
- artifact paths

Run it from the terminal:

```bash
research-ai-local --config local_ai.config.json memory
```

This does not approve, revise, export, or delete anything. It turns failed and review-gated runs into inspectable operational memory.

## Safety Boundaries

- Model output remains draft-only until review.
- Model switching does not approve or finalize output.
- Degraded, uncertain, failed, or unsupported source handling routes to review.
- Failed branches remain inspectable artifacts.
- The local console only runs whitelisted actions.

## Why This Is Useful

The architecture plan makes the system easier to inspect before running a task. A researcher can see:

- which backend is primary
- which backend is used for review or fallback
- whether configured models are actually effective
- which stages preserve review gates
- where failed outputs should remain visible

This is a model-ceiling improvement because stronger models can be swapped in later without weakening the verification workflow.
