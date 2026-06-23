from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from carwash.export.gates import validate_public_artifact
from carwash.schemas import BoundaryAssessment, Case, Claim, PublicationArtifact, PublicationExportStatus, Source


class ExportBlockedError(RuntimeError):
    def __init__(self, assessment: BoundaryAssessment) -> None:
        super().__init__("export blocked: " + "; ".join(assessment.reasons))
        self.assessment = assessment


def build_public_json(
    *,
    artifact: PublicationArtifact,
    case: Case,
    claims: list[Claim],
    sources: list[Source],
) -> dict[str, Any]:
    assessment = validate_public_artifact(artifact, case, claims, sources)
    if not assessment.allowed:
        raise ExportBlockedError(assessment)

    claims_by_id = {claim.id: claim for claim in claims}
    sources_by_id = {source.id: source for source in sources}
    used_source_ids = sorted(
        {
            source_id
            for claim_id in artifact.approved_claim_ids
            for source_id in claims_by_id[claim_id].source_ids
        }
    )
    return {
        "artifact_id": artifact.id,
        "case": {
            "id": case.id,
            "title": case.public_title,
            "geography": case.geography,
            "hazards": case.hazard_tags,
            "stage": case.adaptation_stage,
            "lead_org": case.lead_org,
            "seasonal_tags": case.seasonal_tags,
            "transferability_dimensions": case.transferability_dimensions,
        },
        "public_copy": [
            {
                "text": sentence.text,
                "approved_claim_ids": sentence.approved_claim_ids,
            }
            for sentence in artifact.public_copy
        ],
        "approved_claims": [
            {
                "id": claim_id,
                "class": claims_by_id[claim_id].claim_class,
                "locator": claims_by_id[claim_id].locator,
                "source_ids": claims_by_id[claim_id].source_ids,
            }
            for claim_id in artifact.approved_claim_ids
        ],
        "sources": [_source_payload(sources_by_id[source_id]) for source_id in used_source_ids],
        "source_note": artifact.source_note,
        "image_metadata": artifact.image_metadata,
        "accessibility_metadata": artifact.accessibility_metadata,
        "export_status": PublicationExportStatus.EXPORT_READY,
    }


def write_public_json(
    *,
    artifact: PublicationArtifact,
    case: Case,
    claims: list[Claim],
    sources: list[Source],
    output_dir: Path,
) -> Path:
    payload = build_public_json(artifact=artifact, case=case, claims=claims, sources=sources)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{artifact.id}.json"
    output_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return output_path


def _source_payload(source: Source) -> dict[str, Any]:
    fetched_at = source.fetched_at.isoformat() if source.fetched_at is not None else None
    return {
        "id": source.id,
        "url": str(source.url),
        "owner": source.owner,
        "authority": source.authority_level,
        "fetched_at": fetched_at,
    }
