# Model Ceiling Strategy

The project should improve model capability without weakening review gates.

## Current Local Constraint

On the current machine, Ollama is reachable and lists `qwen2.5:7b`, but generation fails with:

```text
llama runner process has terminated
```

LM Studio is reachable and can be used as a fallback, but the currently loaded Qwen model may return reasoning content without a final answer. The local quality gate detects this and blocks final use.

## Practical Upgrade Paths

### 1. Stabilize The Local Backend

- restart Ollama
- reinstall or re-pull the failing model
- test a smaller model first
- test a stronger but stable model only after small-model generation works
- keep generation token limits explicit

### 2. Use LM Studio As A Review/Fallback Backend

- verify the selected model returns final `content`, not only `reasoning_content`
- use the model status command before runs
- keep every fallback attempt in `request.json`

### 3. Add Optional Remote Evaluation

If local generation remains unstable, use a stronger external model only for gated draft generation or benchmark replay. Required constraints:

- no private data unless explicitly approved
- source excerpts must be intentionally selected
- outputs remain review-gated
- replay reports compare candidate output to historical reviewed data

### 4. Push Theory And Workflow When Model Testing Fails

If no model backend is reliable, continue improving:

- source extraction
- source profiles
- deterministic research-idea scaffolds
- benchmark replay
- schema validation
- review packet design
- failure diagnostics
- evaluation rubrics

These improvements raise the system ceiling because they make future model outputs more testable and less costly to review.

## Target Standard

The system should not claim perfect model accuracy. The standard is:

- every source is traceable
- every generated idea has review status
- every benchmark comparison is reproducible
- every failure is preserved as an inspectable artifact
- final research use requires validation and human judgment
