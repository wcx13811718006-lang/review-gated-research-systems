# External Agent Patterns

This project can learn from current open-source agent systems without copying their stacks wholesale. The goal is to borrow patterns that strengthen local research work, review gates, traceability, and validation.

Last checked: 2026-04-29.

## References

- [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
- [openclaw/openclaw](https://github.com/openclaw/openclaw)
- [ResearAI/DeepScientist](https://github.com/ResearAI/DeepScientist)
- [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)
- [microsoft/autogen](https://github.com/microsoft/autogen)
- [OpenHands/OpenHands](https://github.com/OpenHands/OpenHands)
- [CrewAI open source](https://www.crewai.com/open-source)
- [Google Research AI co-scientist](https://research.google/blog/accelerating-scientific-breakthroughs-with-an-ai-co-scientist)

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

### 6. Findings Memory Without Full Autonomy

DeepScientist emphasizes long-horizon research work, findings memory, experiment logs, and preserving failed branches. For this project, the useful pattern is a smaller local abstraction:

- preserve accepted findings, rejected findings, and failed extraction/model attempts
- keep failed branches inspectable instead of overwriting them
- link each idea or coded output back to source excerpts, backend attempts, and review decisions
- promote only reviewed findings into later benchmark or research-memory use

This repository does not adopt DeepScientist's full autonomous discovery loop. The public-safe version keeps human review and schema validation as the controlling layer.

### 7. Scientific-Method-Inspired Agent Roles

Google's AI co-scientist describes a multi-agent research assistant organized around generation, reflection, ranking, evolution, proximity, and meta-review. The useful local pattern is to separate research work into visible roles:

- generate candidate ideas or coded drafts
- reflect on source support and missing evidence
- rank candidates by review readiness
- preserve alternate branches instead of overwriting them
- meta-review whether a result is ready for human inspection

This repository should not claim autonomous scientific discovery. It can borrow the role separation while keeping each stage inspectable and review-gated.

### 8. Durable State Instead Of Hidden Chains

LangGraph's useful pattern is not a dependency requirement. The pattern is that long-running work should have explicit state transitions, durable checkpoints, and human inspection points. In this repository, the local equivalent is:

- source intake
- draft generation
- review/fallback backend check
- deterministic quality gate
- artifact memory
- human review

The new local model-architecture planner exposes these stages in the CLI and console without replacing the existing workflow.

### 9. Observable Execution Rather Than Broad Autonomy

OpenHands and similar coding agents make execution state visible through logs, process status, and artifacts. The useful pattern here is narrow observability:

- show which backend and model were selected
- show which task is running
- preserve stdout/stderr tails
- keep request and review-gate artifacts inspectable

The public showcase does not adopt broad autonomous filesystem or application control.

## Patterns Not Borrowed Yet

- remote messaging gateways
- autonomous tool execution across apps
- cron-driven unattended research actions
- self-modifying skills
- broad filesystem automation
- cloud agent hosting
- full autonomous discovery loops
- opaque multi-agent self-improvement

These can be useful later, but only after the local review-gated workflow is reliable on historical data.

## Integration Order

1. Historical replay benchmark against already reviewed data.
2. Source extraction reliability for DOCX/PDF/CSV.
3. Structured output skills with schema-locked validation.
4. Review memory from accepted corrections.
5. Project status surfaces.
6. Findings memory for accepted, rejected, and failed branches.
7. Research-role separation: generation, reflection, ranking, and meta-review.
8. Optional automation with explicit approval and sandboxing.
