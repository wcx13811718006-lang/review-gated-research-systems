# Token Cost Control

Token reduction is useful, but it is lossy. In a legal or research workflow, compression should reduce draft-generation cost without weakening final evidence review.

This repository uses a conservative two-layer design:

- built-in extractive compression that requires no external dependency
- optional LLMLingua support when the package is installed

Compression is disabled by default for `ask` and `ideate`. Turn it on only after checking that the compressed context still preserves the relevant evidence.

## Install Optional LLMLingua Support

Inside a virtual environment:

```bash
python3 -m pip install -e ".[token-compression]"
```

The optional dependency installs `llmlingua`. The first use may still need model downloads depending on LLMLingua configuration and local cache state.

## Compress One Source Manually

```bash
research-ai-local --config local_ai.config.json compress \
  --source README.md \
  --query "review-gated research workflow" \
  --target-tokens 300 \
  --method auto \
  --output-dir /tmp/research_ai_compression_smoke
```

`--method auto` uses the safe built-in extractive compressor. This avoids accidental large model downloads. Use `--method llmlingua` only when you explicitly want to invoke the optional plugin and accept its model/cache requirements.

## Enable Compression For Draft Runs

In `local_ai.config.json`:

```json
{
  "prompt_compression": {
    "enabled": true,
    "method": "auto",
    "ratio": 0.65,
    "target_tokens": null
  }
}
```

Then run:

```bash
research-ai-local --config local_ai.config.json ask "Draft a review-gated answer." --source README.md
```

Each run records compression metadata in `request.json`:

- enabled / disabled
- method used
- plugin availability
- origin token estimate
- compressed token estimate
- compression ratio
- lossy compression warning

## Rules For Legal And Research Use

- Do not compress source material used for final evidence review.
- Use compression for draft generation, triage, or ideation only.
- Keep original source files linked and inspectable.
- If compression removes party names, dates, legal issues, citations, or coding fields, disable compression for that task.
- Never treat a compressed-context answer as final without human review.

## External Reference

LLMLingua is a Microsoft Research prompt-compression method that uses a smaller model to remove lower-information tokens while preserving task-relevant context. It is useful for cost reduction, but the tradeoff must be validated for each workflow. In this project, LLMLingua is an explicit opt-in method rather than the automatic default.
