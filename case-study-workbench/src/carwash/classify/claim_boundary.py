from __future__ import annotations

from carwash.schemas import (
    BoundaryAssessment,
    Case,
    Claim,
    ClaimClass,
    OwnerType,
    ProjectStatusAtSource,
    ReviewRoute,
    Source,
    SourceAuthority,
    SupportStatus,
)

COMPLETION_TERMS = (
    "completed",
    "operational",
    "operating",
    "is open",
    "now serves",
    "delivered",
    "achieved",
    "reduced flooding",
    "reduced heat",
    "reduced smoke",
    "increased water supply",
)


def assess_claim_boundary(claim: Claim, case: Case, sources: list[Source]) -> BoundaryAssessment:
    """Return publication boundary assessment for one claim.

    The rules are intentionally conservative. They block transformations that the
    implementation spec calls out as high-risk and route sensitive claims to human review.
    """

    indexed_sources = {source.id: source for source in sources}
    claim_sources = [indexed_sources[source_id] for source_id in claim.source_ids if source_id in indexed_sources]
    text = claim.text.lower()
    reasons: list[str] = []
    route = claim.required_review

    if not claim.source_ids:
        reasons.append("missing claim-source mapping")
        return BoundaryAssessment(allowed=False, route=ReviewRoute.BLOCKED_EXPORT, reasons=reasons)

    if not claim_sources:
        reasons.append("claim references unavailable source IDs")
        return BoundaryAssessment(allowed=False, route=ReviewRoute.BLOCKED_EXPORT, reasons=reasons)

    if claim.support_status in {SupportStatus.UNSUPPORTED, SupportStatus.PARKED}:
        reasons.append(f"claim support status is {claim.support_status}")

    for source in claim_sources:
        if source.fetch_status in {"failed", "blocked", "parked"}:
            reasons.append(f"source {source.id} is not verified")

        if (
            source.project_status_at_source
            in {
                ProjectStatusAtSource.PLANNED,
                ProjectStatusAtSource.FUNDED,
                ProjectStatusAtSource.IN_DEVELOPMENT,
            }
            and claim.claim_class
            in {
                ClaimClass.IMPLEMENTATION_ACTIVITY,
                ClaimClass.PROGRAM_REPORTED_OUTPUT,
                ClaimClass.MEASURED_OUTCOME,
            }
            and any(term in text for term in COMPLETION_TERMS)
        ):
            reasons.append(
                "planned/funded/in-development source cannot support completion, operation, or outcome wording"
            )

        if (
            source.source_type == "funding_announcement"
            and claim.claim_class
            in {ClaimClass.IMPLEMENTATION_ACTIVITY, ClaimClass.MEASURED_OUTCOME}
            and any(term in text for term in ("operating", "operational", "now serves", "reduced"))
        ):
            reasons.append("funding announcement cannot be transformed into operating facility or outcome claim")

        if source.project_status_at_source == ProjectStatusAtSource.PORTFOLIO and (
            claim.claim_class == ClaimClass.MEASURED_OUTCOME or "local_outcome_from_portfolio" in claim.risk_flags
        ):
            reasons.append("portfolio aggregate metrics cannot be assigned to a local case")

        if (
            "Tribal/Nation-led" in case.sensitivity_flags
            and source.owner_type != OwnerType.NATION_TRIBE
            and source.authority_level == SourceAuthority.SUPPORTING
            and "overrides_nation_wording" in claim.risk_flags
        ):
            reasons.append("supporting source cannot override Nation-authored public wording")

    if _requires_mandatory_review(case, claim):
        route = ReviewRoute.MANDATORY_FULL_REVIEW

    allowed = not reasons and claim.support_status == SupportStatus.APPROVED
    if reasons:
        route = ReviewRoute.BLOCKED_EXPORT
    elif route == ReviewRoute.MANDATORY_FULL_REVIEW and claim.support_status != SupportStatus.APPROVED:
        allowed = False
        reasons.append("mandatory review has not approved this claim")

    return BoundaryAssessment(allowed=allowed, route=route, reasons=reasons)


def _requires_mandatory_review(case: Case, claim: Claim) -> bool:
    mandatory_flags = {
        "Tribal/Nation-led",
        "cultural knowledge",
        "data sovereignty",
        "relocation",
        "public health",
        "smoke",
        "fisheries",
        "wetlands",
        "hydrology",
        "flooding",
        "sea-level rise",
        "engineering",
        "legal/safety",
    }
    if set(case.sensitivity_flags) & mandatory_flags:
        return True
    return claim.claim_class == ClaimClass.MEASURED_OUTCOME

