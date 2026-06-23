from __future__ import annotations

from carwash.classify.claim_boundary import assess_claim_boundary
from carwash.schemas import (
    BoundaryAssessment,
    Case,
    Claim,
    PublicationArtifact,
    ReviewRoute,
    Source,
)


def validate_public_artifact(
    artifact: PublicationArtifact,
    case: Case,
    claims: list[Claim],
    sources: list[Source],
) -> BoundaryAssessment:
    reasons: list[str] = []
    claims_by_id = {claim.id: claim for claim in claims}

    for idx, sentence in enumerate(artifact.public_copy, start=1):
        if not sentence.approved_claim_ids:
            reasons.append(f"public sentence {idx} has no approved claim ID")
        for claim_id in sentence.approved_claim_ids:
            if claim_id not in claims_by_id:
                reasons.append(f"public sentence {idx} references unknown claim {claim_id}")

    for claim_id in artifact.approved_claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim is None:
            reasons.append(f"artifact references unknown approved claim {claim_id}")
            continue
        assessment = assess_claim_boundary(claim, case, sources)
        if not assessment.allowed:
            if assessment.reasons:
                reasons.extend([f"{claim_id}: {reason}" for reason in assessment.reasons])
            else:
                reasons.append(f"{claim_id}: claim is not approved for export")

    if not artifact.image_metadata.get("alt_text") or not artifact.image_metadata.get("rights_status"):
        reasons.append("missing image rights or alt text")

    if reasons:
        return BoundaryAssessment(allowed=False, route=ReviewRoute.BLOCKED_EXPORT, reasons=reasons)
    return BoundaryAssessment(allowed=True, route=ReviewRoute.NONE, reasons=[])
