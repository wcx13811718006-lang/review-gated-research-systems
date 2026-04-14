# Demo Guide

This folder contains the shortest inspection path for the public showcase.

## Quick Run

From the repository root:

```bash
python3 demo/run_demo.py
```

## Fast Inspection Path

1. Sample inputs:
   [`sample_inputs/sample_links.csv`](./sample_inputs/sample_links.csv),
   [`sample_inputs/sample_metadata.json`](./sample_inputs/sample_metadata.json),
   [`sample_inputs/sample_pdf_placeholder.txt`](./sample_inputs/sample_pdf_placeholder.txt)
2. Routing decision:
   [`sample_outputs/routing_decisions.json`](./sample_outputs/routing_decisions.json)
3. Review packet:
   [`sample_outputs/review_packet.md`](./sample_outputs/review_packet.md)
4. Analysis-ready export:
   [`sample_outputs/final_export.json`](./sample_outputs/final_export.json)
5. Status surface:
   [`sample_outputs/system_status.csv`](./sample_outputs/system_status.csv)

## What The Demo Is Showing

- one record that clears the gate
- one record that remains review-gated because metadata is incomplete
- one record that remains review-gated because document quality is degraded

## Public-Safe Scope

The demo is intentionally small and sanitized. It is designed to illustrate workflow behavior, not to claim a full operational research system or domain-complete document handling.
