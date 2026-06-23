from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ClaimClass(StrEnum):
    CONTEXT = "context"
    PLANNED_ACTION = "planned_action"
    FUNDED_ACTION = "funded_action"
    IMPLEMENTATION_ACTIVITY = "implementation_activity"
    PROGRAM_REPORTED_OUTPUT = "program_reported_output"
    MODELED_BENEFIT = "modeled_benefit"
    MEASURED_OUTCOME = "measured_outcome"
    LESSON_LEARNED = "lesson_learned"
    TRANSFERABILITY_CONDITION = "transferability_condition"
    UNCERTAINTY = "uncertainty"
    PROHIBITED_PUBLIC_CLAIM = "prohibited_public_claim"


class SupportStatus(StrEnum):
    UNSUPPORTED = "unsupported"
    SOURCE_SUPPORTED = "source_supported"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    PARKED = "parked"


class ReviewRoute(StrEnum):
    NONE = "none"
    RANDOM_AUDIT = "random_audit"
    TARGETED_REVIEW = "targeted_review"
    MANDATORY_FULL_REVIEW = "mandatory_full_review"
    BLOCKED_EXPORT = "blocked_export"


class ReviewDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    PARKED = "parked"


class SourceAuthority(StrEnum):
    PRIMARY = "primary"
    SUPPORTING = "supporting"
    DISCOVERY_ONLY = "discovery_only"
    INSUFFICIENT = "insufficient"


class OwnerType(StrEnum):
    NATION_TRIBE = "nation_tribe"
    GOVERNMENT = "government"
    IMPLEMENTING_ORG = "implementing_org"
    UNIVERSITY = "university"
    NGO = "ngo"
    NEWS = "news"
    UNKNOWN = "unknown"


class FetchStatus(StrEnum):
    VERIFIED = "verified"
    FAILED = "failed"
    PARKED = "parked"
    BLOCKED = "blocked"
    NOT_FETCHED = "not_fetched"


class ProjectStatusAtSource(StrEnum):
    PLANNED = "planned"
    FUNDED = "funded"
    IN_DEVELOPMENT = "in_development"
    IMPLEMENTING = "implementing"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    PORTFOLIO = "portfolio"
    UNKNOWN = "unknown"


class PublicationExportStatus(StrEnum):
    DRAFT = "draft"
    REVIEW_REQUIRED = "review_required"
    EXPORT_READY = "export_ready"
    BLOCKED = "blocked"


class ParsedDocumentKind(StrEnum):
    HTML = "html"
    PDF = "pdf"
    TEXT = "text"


class Case(StrictModel):
    id: Annotated[str, Field(pattern=r"^[A-Z]{2}_[A-Z]+_[0-9]{3}$")]
    title: str
    public_title: str
    geography: str
    hazard_tags: list[str]
    adaptation_stage: str
    action: str
    lead_org: str
    partner_orgs: list[str] = Field(default_factory=list)
    status: str
    sensitivity_flags: list[str] = Field(default_factory=list)
    seasonal_tags: list[str] = Field(default_factory=list)
    transferability_dimensions: list[str] = Field(default_factory=list)

    @field_validator("hazard_tags", "seasonal_tags", "transferability_dimensions")
    @classmethod
    def require_non_empty_list(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("list must not be empty")
        return value


class Source(StrictModel):
    id: str
    case_id: str
    url: AnyUrl
    owner: str
    owner_type: OwnerType
    authority_level: SourceAuthority
    source_type: str
    fetched_at: date | None = None
    published_at: date | None = None
    content_hash: str | None = None
    snapshot_uri: str | None = None
    fetch_status: FetchStatus
    project_status_at_source: ProjectStatusAtSource = ProjectStatusAtSource.UNKNOWN
    evidence_supported: str
    rights_notes: str | None = None


class Claim(StrictModel):
    id: str
    case_id: str
    text: str
    claim_class: ClaimClass
    source_ids: list[str] = Field(default_factory=list)
    locator: str | None = None
    support_status: SupportStatus
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    risk_flags: list[str] = Field(default_factory=list)
    required_review: ReviewRoute = ReviewRoute.NONE
    reviewer: str | None = None


class Review(StrictModel):
    id: str
    object_type: str
    object_id: str
    route: ReviewRoute
    reviewer_role: str
    decision: ReviewDecision = ReviewDecision.PENDING
    note: str
    timestamp: datetime | None = None


class PublicationSentence(StrictModel):
    text: str
    approved_claim_ids: list[str]


class PublicationArtifact(StrictModel):
    id: str
    case_id: str
    version: str
    public_copy: list[PublicationSentence]
    source_note: str
    image_metadata: dict[str, str | None] = Field(default_factory=dict)
    accessibility_metadata: dict[str, str | None] = Field(default_factory=dict)
    approved_claim_ids: list[str]
    export_status: PublicationExportStatus = PublicationExportStatus.DRAFT


class SeasonalContext(StrictModel):
    effective_date: date
    season: str
    hazard_context: str
    data_source: str
    fetched_at: datetime | None = None
    freshness: str
    editorial_status: str


class BoundaryAssessment(StrictModel):
    allowed: bool
    route: ReviewRoute
    reasons: list[str] = Field(default_factory=list)


class ParsedSection(StrictModel):
    locator: str
    heading: str | None = None
    text: str


class ParsedDocument(StrictModel):
    source_id: str
    canonical_url: str
    kind: ParsedDocumentKind
    title: str | None = None
    sections: list[ParsedSection]
    extracted_at: datetime


class ExtractionField(StrictModel):
    value: str | None
    source_locator: str | None = None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)] = 0.0
    review_required: bool = True
    note: str | None = None


class ExtractedSourceMetadata(StrictModel):
    source_id: str
    title: ExtractionField
    owner: ExtractionField
    location: ExtractionField
    project_status: ExtractionField
    published_or_project_date: ExtractionField
    modified_date: ExtractionField


class ReviewQueueItem(StrictModel):
    id: str
    case_id: str
    case_title: str
    claim_id: str
    claim_text: str
    claim_class: ClaimClass
    route: ReviewRoute
    reviewer_role: str
    decision: ReviewDecision
    note: str
    source_ids: list[str]
    source_summaries: list[dict[str, str | None]]
    locator: str | None
    risk_flags: list[str]
