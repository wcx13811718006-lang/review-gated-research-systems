# Data Dictionary

## Case

Represents a bounded adaptation case candidate.

Required fields include stable ID, title, geography, hazard tags, stage, action,
lead organization, sensitivity flags, seasonal tags, and transferability
dimensions.

## Source

Represents one retrievable evidence source.

Key fields:

- `id`: stable source ID
- `case_id`: linked case
- `url`: canonical URL
- `owner`: source owner
- `owner_type`: Nation/Tribe, government, university, NGO, news, or unknown
- `authority_level`: primary, supporting, discovery-only, or insufficient
- `project_status_at_source`: planned, funded, in development, implementing, monitoring, completed, portfolio, or unknown
- `fetch_status`: verified, failed, parked, blocked, or not fetched
- `content_hash` and `snapshot_uri`: required before evidence locking

## Claim

Represents one public or internal statement with evidence lineage.

Key fields:

- `claim_class`: context, planned action, funded action, implementation activity, program-reported output, modeled benefit, measured outcome, lesson learned, transferability condition, uncertainty, or prohibited public claim
- `source_ids`: one or more supporting sources
- `locator`: page, section, table, or PDF locator
- `support_status`: unsupported, source-supported, review-required, approved, or parked
- `risk_flags`: status inflation, funding-to-operation, portfolio-to-local-outcome, Nation wording override, and related flags

## PublicationArtifact

Represents a draft or export-ready public card. Every sentence in `public_copy`
must carry approved claim IDs. Missing claim IDs, missing image rights, missing
alt text, unresolved mandatory review, or failed sources block export.

