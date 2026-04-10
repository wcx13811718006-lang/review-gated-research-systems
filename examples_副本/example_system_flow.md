# Example System Flow

This example mirrors the public demo:

1. A small batch of toy sources enters the system.
2. The routing layer assigns each record to an initial lane based on source type.
3. The validation layer checks metadata completeness and extraction quality.
4. Clean records move into an analysis-ready export.
5. Uncertain records move into a structured review packet for human inspection.
6. Approved records also feed a short analysis brief so later research tasks can start from a clearly scoped handoff.

The key idea is that validation changes system state. It does not merely record diagnostics after the fact.
