from __future__ import annotations

from enum import StrEnum


class CaseWorkflowState(StrEnum):
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    PARSED = "parsed"
    EXTRACTED = "extracted"
    EVIDENCE_LOCKED = "evidence_locked"
    DRAFT_GENERATED = "draft_generated"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    PARKED = "parked"
    EXPORT_READY = "export_ready"


ALLOWED_TRANSITIONS: dict[CaseWorkflowState, set[CaseWorkflowState]] = {
    CaseWorkflowState.DISCOVERED: {CaseWorkflowState.FETCHED, CaseWorkflowState.PARKED},
    CaseWorkflowState.FETCHED: {CaseWorkflowState.PARSED, CaseWorkflowState.PARKED},
    CaseWorkflowState.PARSED: {CaseWorkflowState.EXTRACTED, CaseWorkflowState.PARKED},
    CaseWorkflowState.EXTRACTED: {CaseWorkflowState.EVIDENCE_LOCKED, CaseWorkflowState.REVIEW_REQUIRED},
    CaseWorkflowState.EVIDENCE_LOCKED: {CaseWorkflowState.DRAFT_GENERATED, CaseWorkflowState.REVIEW_REQUIRED},
    CaseWorkflowState.DRAFT_GENERATED: {CaseWorkflowState.REVIEW_REQUIRED},
    CaseWorkflowState.REVIEW_REQUIRED: {
        CaseWorkflowState.APPROVED,
        CaseWorkflowState.CHANGES_REQUESTED,
        CaseWorkflowState.PARKED,
    },
    CaseWorkflowState.CHANGES_REQUESTED: {CaseWorkflowState.EXTRACTED, CaseWorkflowState.PARKED},
    CaseWorkflowState.APPROVED: {CaseWorkflowState.EXPORT_READY},
    CaseWorkflowState.PARKED: {CaseWorkflowState.DISCOVERED},
    CaseWorkflowState.EXPORT_READY: set(),
}


def can_transition(current: CaseWorkflowState, target: CaseWorkflowState) -> bool:
    """Publishing is intentionally absent; publication can only be confirmed by external CMS/manual flow."""

    return target in ALLOWED_TRANSITIONS[current]

