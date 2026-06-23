# Architecture

## Product definition

CAR-WASH is an evidence-first case-study workbench. It discovers and refreshes
candidate sources, snapshots source material, extracts structured fields, maps
public sentences to claims, routes risky material for human review, and exports
approved data for a CMS or static prototype.

It does not approve or publish content automatically.

## MVP flow

1. Seed known candidate cases from workbook review.
2. Register official and supporting sources.
3. Fetch and snapshot sources with hash and timestamp metadata.
4. Parse HTML/PDF content while preserving locators.
5. Extract fields into `Case`, `Source`, and `Claim` objects.
6. Classify claim boundaries.
7. Route claims and cards to human review.
8. Export only approved publication artifacts.

## State model

```text
discovered
-> fetched
-> parsed
-> extracted
-> evidence_locked
-> draft_generated
-> review_required
-> approved / changes_requested / parked
-> export_ready
```

There is no automatic `published` state. Publication must be confirmed by a CMS
or manual workflow outside this pipeline.

## Storage

MVP storage should start with versioned JSON plus SQLite once the review flow is
stable. Postgres is deferred until multi-user operations are confirmed.

## Public prototype

The public prototype should consume generated approved JSON only. It should not
call the scraper or rewrite case text at runtime.

