# Quality Guardrails

The project should optimize for trustworthy workflow behavior, not unsupported claims of perfect model accuracy.

## Practical Standard

The system can guarantee that unreviewed model output is blocked from final export. It cannot guarantee that a local language model is always factually correct.

## Guardrails Implemented In The Local Layer

- outputs are draft by default
- every local AI run writes an audit trail
- backend availability and model mismatch are surfaced explicitly
- source context is tracked in the request artifact
- review gates block final export unless explicitly cleared
- missing source context or backend errors route to review

## What Counts As Ready

A result should become analysis-ready only after:

1. the source material is inspectable
2. the generated answer is traceable to that source material
3. uncertainty is visible
4. a human reviewer accepts or revises the output
5. the export schema is checked before downstream use

## Performance Direction

Performance should improve by reducing wasted work, not by weakening gates:

- cache extracted source context
- reuse backend status checks within a run
- batch independent review items
- keep structured artifacts small and inspectable
- route weak records early instead of repeatedly asking the model

