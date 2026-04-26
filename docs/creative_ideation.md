# Creative Ideation Mode

Creative ideation is a review-gated feature for turning literature or legal documents into plausible research starting points.

It is not a conclusion generator. It is a structured way to extract source cues, propose research directions, and preserve uncertainty for human review.

## Command

```bash
research-ai-local --config local_ai.config.json ideate \
  "Generate research ideas about climate litigation and investment risk." \
  --source "/path/to/literature_or_legal_document.pdf" \
  --ideas 5
```

Dry-run mode verifies source extraction and artifact writing without calling a model:

```bash
research-ai-local --config configs/local_ai.example.json ideate \
  "Smoke test ideation." \
  --source README.md \
  --output-dir /tmp/research_ai_ideation_smoke \
  --dry-run
```

## Artifacts

Each ideation run writes:

- `request.json`: source files, backend status, source preview, generation attempts
- `source_profile.json`: lightweight extracted keywords and evidence sentence candidates
- `idea_scaffold.md`: deterministic theory-grounded idea scaffold, available even when model generation fails
- `idea_brief.md`: model-generated ideation draft, if generation succeeds
- `review_gate.json`: quality and review status
- `manifest.json`: artifact index

## Quality Rules

Ideas must remain grounded in the supplied source context. A useful idea should include:

- source takeaways
- research question
- plausible mechanism
- data or evidence path
- method option
- verification risks
- next review step

The system keeps all ideation output review-gated by default.

If the local model cannot produce a usable final answer, use `idea_scaffold.md` as the fallback starting point. It is generated from source cues and fixed research-design templates, so it is less creative than a strong model, but it remains traceable and reviewable.

## Connection To Evaluation Theory

A locally supplied paper on evaluation/production decoupling argues that evaluation can be separated from production when quality-relevant product attributes are visible, but decoupling becomes unsafe when quality depends on hidden production-process attributes.

This project applies that principle directly:

- AI may produce candidate ideas.
- Human review evaluates whether the idea is grounded, feasible, and worth pursuing.
- The system records source context, generation attempts, and review gates so evaluation is not blind.
- When process signals are missing, outputs remain gated.
