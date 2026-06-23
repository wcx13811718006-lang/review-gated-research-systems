from __future__ import annotations

from pathlib import Path

import fitz
import httpx
import pytest

from carwash.classify.claim_boundary import assess_claim_boundary
from carwash.classify.claim_extraction import build_claims_from_document, classify_claim_text
from carwash.export.public_json import ExportBlockedError, build_public_json
from carwash.extract.metadata import extract_source_metadata
from carwash.fetch.client import fetch_and_snapshot, fetch_url
from carwash.parse.document import parse_html, parse_pdf
from carwash.review.queue import build_review_queue
from carwash.schemas import (
    ClaimClass,
    FetchStatus,
    ProjectStatusAtSource,
    ReviewRoute,
    SupportStatus,
)
from carwash.source_registry import normalize_url, status_from_http, write_snapshot

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_url_normalization_and_http_status_policy():
    assert normalize_url("HTTPS://Example.org/path/?utm_source=x&b=2&a=1") == "https://example.org/path?a=1&b=2"
    assert status_from_http(404) == FetchStatus.PARKED
    assert status_from_http(503) == FetchStatus.FAILED


def test_snapshot_detects_changed_content(tmp_path):
    first = write_snapshot(
        source_id="SRC_EXAMPLE_001",
        url="https://example.org/report.pdf",
        content=b"version one",
        snapshot_root=tmp_path,
    )
    second = write_snapshot(
        source_id="SRC_EXAMPLE_001",
        url="https://example.org/report.pdf",
        content=b"version two",
        snapshot_root=tmp_path,
        previous_hash=first.content_hash,
    )

    assert first.content_hash != second.content_hash
    assert second.changed
    assert second.snapshot_path.endswith(".pdf")


@pytest.mark.anyio
async def test_fetch_adapter_uses_injected_client_and_snapshots_verified_content(tmp_path):
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"verified", request=request))
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        fetched = await fetch_url("https://example.org/demo?utm_source=x", client=client)

    assert fetched.fetch_status == FetchStatus.VERIFIED
    assert fetched.canonical_url == "https://example.org/demo"

    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        result = await fetch_and_snapshot(
            source_id="SRC_EXAMPLE_001",
            url="https://example.org/demo",
            snapshot_root=tmp_path,
            client=client,
        )

    assert result.snapshot is not None
    assert result.snapshot.changed


def test_html_and_pdf_parsing_preserve_locators():
    parsed_html = parse_html(
        "SRC_EXAMPLE_001",
        "https://example.org/resilience-center",
        (FIXTURES / "sample_case.html").read_bytes(),
    )
    metadata = extract_source_metadata(parsed_html)

    assert metadata.project_status.value == "Funded"
    assert metadata.project_status.source_locator == "html:p[3]"
    assert metadata.modified_date.value == "2026-06-20"

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Status: Planned\nLocation: Example County")
    pdf_bytes = doc.tobytes()
    doc.close()
    parsed_pdf = parse_pdf("SRC_EXAMPLE_PDF", "https://example.org/report.pdf", pdf_bytes)

    assert parsed_pdf.sections[0].locator == "pdf:page=1"


def test_claim_classification_and_boundary_controls(make_case, make_source, make_claim):
    claim_class, risk_flags = classify_claim_text(
        "The funded facility is now operating as a resilience center."
    )
    assert claim_class == ClaimClass.FUNDED_ACTION
    assert risk_flags == ["funding_to_operation"]

    source = make_source(project_status_at_source=ProjectStatusAtSource.FUNDED)
    risky_claim = make_claim(
        text="The funded facility is now operating as a resilience center.",
        claim_class=ClaimClass.IMPLEMENTATION_ACTIVITY,
        risk_flags=["funding_to_operation"],
        support_status=SupportStatus.SOURCE_SUPPORTED,
    )
    assessment = assess_claim_boundary(risky_claim, make_case(), [source])

    assert not assessment.allowed
    assert assessment.route == ReviewRoute.BLOCKED_EXPORT


def test_review_queue_and_approved_json_export(make_case, make_source, make_claim, make_public_artifact):
    case = make_case()
    source = make_source()
    claim = make_claim()

    queue = build_review_queue(cases=[case], claims=[claim], sources=[source], random_audit_rate=1)
    assert queue[0].route == ReviewRoute.RANDOM_AUDIT

    payload = build_public_json(
        artifact=make_public_artifact(),
        case=case,
        claims=[claim],
        sources=[source],
    )
    assert payload["case"]["id"] == "EX_CASE_001"
    assert payload["approved_claims"][0]["id"] == "CLM_EXAMPLE_001"

    unapproved = claim.model_copy(update={"support_status": SupportStatus.REVIEW_REQUIRED})
    with pytest.raises(ExportBlockedError):
        build_public_json(
            artifact=make_public_artifact(),
            case=case,
            claims=[unapproved],
            sources=[source],
        )


def test_claim_builder_maps_locator_and_source_without_approval():
    parsed = parse_html(
        "SRC_EXAMPLE_001",
        "https://example.org/demo",
        "<html><body><p>The project is funded. It is not yet operational.</p></body></html>",
    )
    claims = build_claims_from_document(
        parsed,
        case_id="EX_CASE_001",
        source_id="SRC_EXAMPLE_001",
        id_prefix="CLM_PUBLIC",
    )

    assert claims[0].locator == "html:p[1]"
    assert claims[0].source_ids == ["SRC_EXAMPLE_001"]
    assert claims[0].support_status == SupportStatus.SOURCE_SUPPORTED
    assert claims[0].support_status != SupportStatus.APPROVED
