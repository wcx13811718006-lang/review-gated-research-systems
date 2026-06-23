from __future__ import annotations

import re
from collections.abc import Iterable

from carwash.schemas import ExtractedSourceMetadata, ExtractionField, ParsedDocument, ParsedSection

FIELD_PATTERNS: dict[str, re.Pattern[str]] = {
    "owner": re.compile(r"^(?:owner|source owner|lead org(?:anization)?):\s*(?P<value>.+)$", re.I),
    "location": re.compile(r"^(?:location|geography|place):\s*(?P<value>.+)$", re.I),
    "project_status": re.compile(r"^(?:status|project status|stage):\s*(?P<value>.+)$", re.I),
    "published_or_project_date": re.compile(
        r"^(?:published|project date|construction start|adopted):\s*(?P<value>.+)$", re.I
    ),
    "modified_date": re.compile(r"^(?:updated|modified|last modified):\s*(?P<value>.+)$", re.I),
}


def extract_source_metadata(document: ParsedDocument) -> ExtractedSourceMetadata:
    fields = {
        "title": _from_title(document),
        "owner": _find_field(document.sections, "owner"),
        "location": _find_field(document.sections, "location"),
        "project_status": _find_field(document.sections, "project_status"),
        "published_or_project_date": _find_field(document.sections, "published_or_project_date"),
        "modified_date": _find_field(document.sections, "modified_date"),
    }
    return ExtractedSourceMetadata(source_id=document.source_id, **fields)


def _from_title(document: ParsedDocument) -> ExtractionField:
    if not document.title:
        return _missing("title")
    return ExtractionField(
        value=document.title,
        source_locator="html:title[1]" if document.kind == "html" else "pdf:metadata:title",
        confidence=0.95,
        review_required=False,
        note=None,
    )


def _find_field(sections: Iterable[ParsedSection], field_name: str) -> ExtractionField:
    pattern = FIELD_PATTERNS[field_name]
    for section in sections:
        for line in _candidate_lines(section.text):
            match = pattern.match(line)
            if match:
                return ExtractionField(
                    value=match.group("value").strip(),
                    source_locator=section.locator,
                    confidence=0.9,
                    review_required=False,
                    note=None,
                )
    return _missing(field_name)


def _candidate_lines(text: str) -> list[str]:
    pieces = re.split(r"(?:\n|;|\|)", text)
    return [piece.strip() for piece in pieces if piece.strip()]


def _missing(field_name: str) -> ExtractionField:
    return ExtractionField(
        value=None,
        source_locator=None,
        confidence=0.0,
        review_required=True,
        note=f"{field_name} missing; do not guess",
    )

