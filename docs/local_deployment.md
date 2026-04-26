# Local Deployment

This note describes the first local-use layer for the review-gated research assistant. It is intentionally conservative: local model output is treated as draft material until it clears validation and human review.

## What This Adds

- local backend status checks for Ollama and LM Studio
- a command-line `ask` path for research drafts
- durable run artifacts for each local AI call
- a review gate that blocks final export by default
- no dependency on cloud APIs

## Setup

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e .
cp configs/local_ai.example.json local_ai.config.json
```

The example config assumes:

- Ollama at `http://127.0.0.1:11434`
- model `qwen2.5:7b`
- LM Studio at `http://127.0.0.1:1234`, optional for now
- source context is capped at 4,000 characters per file by default for local-model stability

## Check Local Backends

```bash
python3 -m research_systems_showcase.local_ai.cli --config local_ai.config.json status
```

The status output separates:

- configured target model
- discovered available models
- effective selected model
- reachable or unavailable backend state

## Run A Review-Gated Local Draft

```bash
python3 -m research_systems_showcase.local_ai.cli \
  --config local_ai.config.json \
  ask "Summarize the research value of this review-gated workflow." \
  --source README.md
```

The command writes artifacts under `outputs/local_ai_runs/`:

- `request.json`
- `draft_response.md`
- `review_gate.json`
- `manifest.json`

If a backend fails, the error is preserved in the run artifacts. If configured, the local layer can try the review backend as a fallback, but the result remains gated for human review.

## Troubleshooting Backend Behavior

If `status` says a backend is reachable but `ask` still fails, inspect the generated `request.json` artifact. It records each generation attempt.

Observed local failure patterns:

- `llama runner process has terminated`: Ollama accepted the request but the model runner crashed. Check `ollama run <model>` directly, restart Ollama, or switch to a smaller / more stable local model.
- LM Studio returns `reasoning_content` but no final `content`: the model is exposing thinking output without a usable final answer. The local layer marks this as `final_answer_present=false` and keeps the result review-gated.

For stable research use, prefer a model that returns a clear final answer through the normal `content` field.

## Dry-Run Smoke Test

```bash
python3 -m research_systems_showcase.local_ai.cli \
  --config configs/local_ai.example.json \
  ask "Smoke test local artifacts." \
  --source README.md \
  --output-dir /tmp/review_gated_ai_smoke \
  --dry-run
```

## Accuracy Policy

The local assistant does not claim model-perfect accuracy. The operational guarantee is narrower and stronger: generated output is not treated as final unless it clears explicit validation and human review.

This is the correct direction for research work because it preserves uncertainty, source inspection, and reviewer judgment.
