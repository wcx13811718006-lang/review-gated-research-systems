from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from carwash.schemas import (
    Case,
    Claim,
    ClaimClass,
    FetchStatus,
    Review,
    ReviewDecision,
    ReviewRoute,
    Source,
    SourceAuthority,
    SupportStatus,
)

MANDATORY_FLAGS = {
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

TARGETED_RISK_FLAGS = {
    "conflicting_status_date",
    "missing_project_lead",
    "broad_portfolio",
    "uncertain_geography",
    "source_owner_unclear",
    "substantive_diff",
    "status_inflation",
    "funding_to_operation",
    "modeled_not_measured",
    "local_outcome_from_portfolio",
}


def route_claim(
    *,
    case: Case,
    claim: Claim,
    sources: list[Source],
    random_audit_rate: float = 0.2,
) -> ReviewRoute:
    if _is_blocked(claim, sources):
        return ReviewRoute.BLOCKED_EXPORT
    if _needs_mandatory_review(case, claim):
        return ReviewRoute.MANDATORY_FULL_REVIEW
    if _needs_targeted_review(case, claim, sources):
        return ReviewRoute.TARGETED_REVIEW
    if _deterministic_random_audit(claim.id, random_audit_rate):
        return ReviewRoute.RANDOM_AUDIT
    return ReviewRoute.NONE


def create_review(
    *,
    case: Case,
    claim: Claim,
    sources: list[Source],
    reviewer_role: str,
    random_audit_rate: float = 0.2,
) -> Review | None:
    route = route_claim(
        case=case,
        claim=claim,
        sources=sources,
        random_audit_rate=random_audit_rate,
    )
    if route == ReviewRoute.NONE:
        return None
    return Review(
        id=f"REV_{claim.id}",
        object_type="claim",
        object_id=claim.id,
        route=route,
        reviewer_role=reviewer_role,
        decision=ReviewDecision.PENDING,
        note=_route_note(route),
        timestamp=datetime.now(UTC),
    )


def unresolved_required_reviews(reviews: list[Review]) -> list[Review]:
    return [
        review
        for review in reviews
        if review.route
        in {
            ReviewRoute.MANDATORY_FULL_REVIEW,
            ReviewRoute.TARGETED_REVIEW,
            ReviewRoute.BLOCKED_EXPORT,
        }
        and review.decision != ReviewDecision.APPROVED
    ]


def _is_blocked(claim: Claim, sources: list[Source]) -> bool:
    if not claim.source_ids:
        return True
    indexed_sources = {source.id: source for source in sources}
    claim_sources = [indexed_sources.get(source_id) for source_id in claim.source_ids]
    if any(source is None for source in claim_sources):
        return True
    if any(source.fetch_status in {FetchStatus.FAILED, FetchStatus.PARKED, FetchStatus.BLOCKED} for source in claim_sources if source):
        return True
    return claim.support_status in {SupportStatus.UNSUPPORTED, SupportStatus.PARKED}


def _needs_mandatory_review(case: Case, claim: Claim) -> bool:
    return bool(set(case.sensitivity_flags) & MANDATORY_FLAGS) or claim.claim_class == ClaimClass.MEASURED_OUTCOME


def _needs_targeted_review(case: Case, claim: Claim, sources: list[Source]) -> bool:
    del case
    if set(claim.risk_flags) & TARGETED_RISK_FLAGS:
        return True
    for source in sources:
        if source.id in claim.source_ids and source.authority_level in {
            SourceAuthority.SUPPORTING,
            SourceAuthority.INSUFFICIENT,
            SourceAuthority.DISCOVERY_ONLY,
        }:
            return True
    return claim.support_status == SupportStatus.REVIEW_REQUIRED


def _deterministic_random_audit(object_id: str, audit_rate: float) -> bool:
    if audit_rate <= 0:
        return False
    if audit_rate >= 1:
        return True
    digest = hashlib.sha256(object_id.encode("utf-8")).hexdigest()
    bucket = int(digest[:8], 16) / 0xFFFFFFFF
    return bucket < audit_rate


def _route_note(route: ReviewRoute) -> str:
    return {
        ReviewRoute.BLOCKED_EXPORT: "Blocked until missing or unsafe evidence state is resolved.",
        ReviewRoute.MANDATORY_FULL_REVIEW: "Mandatory full review required by sensitivity or measured-outcome rule.",
        ReviewRoute.TARGETED_REVIEW: "Targeted review required by source, uncertainty, or risk flag.",
        ReviewRoute.RANDOM_AUDIT: "Random audit sample for low-risk metadata calibration.",
        ReviewRoute.NONE: "No review required.",
    }[route]

