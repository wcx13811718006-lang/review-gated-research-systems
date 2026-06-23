from __future__ import annotations

import re

from carwash.schemas import Claim, ClaimClass, ParsedDocument, ReviewRoute, SupportStatus

SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")


def split_sentences(text: str) -> list[str]:
    candidates = SENTENCE_END_RE.split(text.strip())
    return [candidate.strip() for candidate in candidates if candidate.strip()]


def classify_claim_text(text: str) -> tuple[ClaimClass, list[str]]:
    lowered = text.lower()
    risk_flags: list[str] = []

    if any(term in lowered for term in ("not yet known", "uncertain", "not known", "requires review")):
        return ClaimClass.UNCERTAINTY, risk_flags

    if any(term in lowered for term in ("modeled", "projected", "estimated", "scenario", "anticipated benefit")):
        return ClaimClass.MODELED_BENEFIT, ["modeled_not_measured"]

    if any(term in lowered for term in ("funded", "award", "grant", "fema")):
        if any(term in lowered for term in ("operating", "operational", "now serves")):
            risk_flags.append("funding_to_operation")
        return ClaimClass.FUNDED_ACTION, risk_flags

    if any(term in lowered for term in ("planned", "proposed", "in development", "intended", "will ")):
        if any(term in lowered for term in ("completed", "operational", "reduced", "achieved")):
            risk_flags.append("status_inflation")
        return ClaimClass.PLANNED_ACTION, risk_flags

    if any(term in lowered for term in ("measured", "observed", "monitored", "reduced", "increased")):
        return ClaimClass.MEASURED_OUTCOME, risk_flags

    if any(term in lowered for term in ("reported", "served", "installed", "removed", "acres")):
        return ClaimClass.PROGRAM_REPORTED_OUTPUT, risk_flags

    if any(term in lowered for term in ("transfer", "depends on", "site-specific", "condition")):
        return ClaimClass.TRANSFERABILITY_CONDITION, risk_flags

    return ClaimClass.CONTEXT, risk_flags


def build_claims_from_document(
    document: ParsedDocument,
    *,
    case_id: str,
    source_id: str,
    id_prefix: str | None = None,
) -> list[Claim]:
    prefix = id_prefix or f"CLM_{case_id}"
    claims: list[Claim] = []
    counter = 1
    for section in document.sections:
        for sentence in split_sentences(section.text):
            claim_class, risk_flags = classify_claim_text(sentence)
            claims.append(
                Claim(
                    id=f"{prefix}_{counter:03d}",
                    case_id=case_id,
                    text=sentence,
                    claim_class=claim_class,
                    source_ids=[source_id],
                    locator=section.locator,
                    support_status=SupportStatus.SOURCE_SUPPORTED,
                    confidence=0.7,
                    risk_flags=risk_flags,
                    required_review=ReviewRoute.TARGETED_REVIEW if risk_flags else ReviewRoute.NONE,
                    reviewer=None,
                )
            )
            counter += 1
    return claims

