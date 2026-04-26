# External Agent Patterns

This project can learn from current open-source agent systems without copying their stacks wholesale. The goal is to borrow patterns that strengthen local research work, review gates, traceability, and validation.

Last checked: 2026-04-25.

## References

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [openclaw/openclaw](https://github.com/openclaw/openclaw)

## Patterns Worth Borrowing

### 1. Memory With Review Boundaries

Hermes emphasizes persistent memory, session search, and skill learning across conversations. For this project, the useful pattern is not autonomous self-belief. The useful pattern is a local memory ledger that preserves:

- what source files were used
- what model/backend was used
- what failed
- what a human accepted or rejected
- what should be reused in later research tasks

Current local implementation:

- every local AI run writes `request.json`
- every run writes `review_gate.json`
- historical benchmark replay writes comparison reports

Next local extension:

- add a review memory index that stores accepted corrections and failed branches as searchable artifacts

### 2. Skills As Procedural Research Routines

Hermes and OpenClaw both expose skill/workspace concepts. For this project, skills should be narrow research routines, not broad autonomous powers.

Good candidate skills:

- summarize a legal document with uncertainty notes
- extract CCLD coding fields into a schema-locked row
- compare model output against a benchmark CSV
- prepare a professor-facing review packet
- audit whether a result is analysis-ready

Each skill should have:

- explicit inputs
- explicit output schema
- local artifacts
- validation checks
- human-review routing

### 3. Multi-Backend Model Routing

Hermes supports provider switching. This project borrows that idea in a narrower way:

- Ollama can be the primary extraction/drafting backend
- LM Studio can be the review/fallback backend
- configured models are compared against discovered models
- backend failures are written into artifacts

Current local implementation:

- `research-ai-local status`
- configured / available / effective model reporting
- fallback attempt recording

### 4. Stateful Workflow Surfaces

OpenClaw and Hermes both prioritize status surfaces. For research work, the equivalent should be project-level status, not a general-purpose assistant dashboard.

Useful surfaces:

- active batch
- sources processed
- sources failed
- review queue
- benchmark comparison status
- final export readiness

### 5. Sandboxed Action Boundaries

OpenClaw documents that main-session tools may run with host access, while non-main/group sessions should use sandboxing. This project should keep a stricter default:

- local model calls are allowed
- source reading is explicit
- output writing is confined to configured artifact directories
- final export remains blocked by validation and review
- no remote messaging, browser automation, file deletion, or scheduled actions by default

## Patterns Not Borrowed Yet

- remote messaging gateways
- autonomous tool execution across apps
- cron-driven unattended research actions
- self-modifying skills
- broad filesystem automation
- cloud agent hosting

These can be useful later, but only after the local review-gated workflow is reliable on historical data.

## Integration Order

1. Historical replay benchmark against already reviewed data.
2. Source extraction reliability for DOCX/PDF/CSV.
3. Structured output skills with schema-locked validation.
4. Review memory from accepted corrections.
5. Project status surfaces.
6. Optional automation with explicit approval and sandboxing.

