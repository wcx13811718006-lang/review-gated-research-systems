from __future__ import annotations

from datetime import date

import pytest

from carwash.schemas import (
    Case,
    Claim,
    ClaimClass,
    FetchStatus,
    OwnerType,
    PublicationArtifact,
    PublicationSentence,
    ReviewRoute,
    Source,
    SourceAuthority,
    SupportStatus,
)


@pytest.fixture
def make_case():
    def factory(**overrides: object) -> Case:
        data = {
            "id": "EX_CASE_001",
            "title": "Example Resilience Center Upgrade",
            "public_title": "Example Resilience Center Upgrade",
            "geography": "Example County, Example State",
            "hazard_tags": ["heat", "smoke"],
            "adaptation_stage": "Funded",
            "action": "Facility upgrade",
            "lead_org": "Example City Resilience Office",
            "partner_orgs": [],
            "status": "demo",
            "sensitivity_flags": [],
            "seasonal_tags": ["summer"],
            "transferability_dimensions": ["facility operations", "accessibility"],
        }
        data.update(overrides)
        return Case.model_validate(data)

    return factory


@pytest.fixture
def make_source():
    def factory(**overrides: object) -> Source:
        data = {
            "id": "SRC_EXAMPLE_001",
            "case_id": "EX_CASE_001",
            "url": "https://example.org/resilience-center",
            "owner": "Example City Resilience Office",
            "owner_type": OwnerType.GOVERNMENT,
            "authority_level": SourceAuthority.PRIMARY,
            "source_type": "funding_announcement",
            "fetched_at": date(2026, 6, 20),
            "published_at": None,
            "content_hash": "abc123",
            "snapshot_uri": "data/snapshots/example.html",
            "fetch_status": FetchStatus.VERIFIED,
            "project_status_at_source": "funded",
            "evidence_supported": "Funding and intent for a future facility upgrade",
            "rights_notes": None,
        }
        data.update(overrides)
        return Source.model_validate(data)

    return factory


@pytest.fixture
def make_claim():
    def factory(**overrides: object) -> Claim:
        data = {
            "id": "CLM_EXAMPLE_001",
            "case_id": "EX_CASE_001",
            "text": "The example city received funding to upgrade a resilience center.",
            "claim_class": ClaimClass.FUNDED_ACTION,
            "source_ids": ["SRC_EXAMPLE_001"],
            "locator": "html:p[3]",
            "support_status": SupportStatus.APPROVED,
            "confidence": 0.9,
            "risk_flags": [],
            "required_review": ReviewRoute.NONE,
            "reviewer": None,
        }
        data.update(overrides)
        return Claim.model_validate(data)

    return factory


@pytest.fixture
def make_public_artifact():
    def factory(**overrides: object) -> PublicationArtifact:
        data = {
            "id": "PUB_EXAMPLE_001",
            "case_id": "EX_CASE_001",
            "version": "public-demo",
            "public_copy": [
                PublicationSentence(
                    text="The example city received funding to upgrade a resilience center.",
                    approved_claim_ids=["CLM_EXAMPLE_001"],
                )
            ],
            "source_note": "Synthetic source note for public demo.",
            "image_metadata": {"rights_status": "approved", "alt_text": "Example facility exterior."},
            "accessibility_metadata": {"reading_order_checked": "true", "reduced_motion_safe": "true"},
            "approved_claim_ids": ["CLM_EXAMPLE_001"],
        }
        data.update(overrides)
        return PublicationArtifact.model_validate(data)

    return factory
