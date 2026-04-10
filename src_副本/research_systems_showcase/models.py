from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SourceRecord:
    record_id: str
    source_type: str
    title: str
    locator: str
    abstract: str
    project_tags: list[str]
    notes: str
    metadata: dict[str, Any] = field(default_factory=dict)
    synthetic_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    record_id: str
    title: str
    source_type: str
    route_lane: str
    decision: str
    decision_reason: str
    review_required: bool
    checks: list[dict[str, Any]]
    downstream_queue: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

