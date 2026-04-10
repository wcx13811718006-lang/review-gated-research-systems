# Example Review Packet

## Summary

This example shows how the public demo pauses uncertain records before downstream analysis.

- `link_platform_adoption` is approved for analysis.
- `link_firm_dynamics` is held for metadata repair.
- `pdf_policy_appendix` is held because the placeholder document is flagged as OCR-suspected.

## Review Questions

- Is the source description complete enough for downstream use?
- Should the record be revised, enriched, or held out of the analysis set?

## Human Checklist

- confirm whether missing citation fields can be filled reliably
- confirm whether the document should go through a richer extraction step
- approve only records that meet downstream readiness standards

For the full generated packet, see `demo/sample_outputs/review_packet.md` after running `python3 demo/run_demo.py`.
