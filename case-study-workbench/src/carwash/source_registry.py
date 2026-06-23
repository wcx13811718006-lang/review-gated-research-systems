from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from carwash.schemas import FetchStatus

TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
PARKED_HTTP_STATUSES = {403, 404, 410, 451}
REDIRECT_LOOP_STATUS = 310


@dataclass(frozen=True)
class SnapshotRecord:
    source_id: str
    canonical_url: str
    content_hash: str
    snapshot_path: str
    fetched_at: datetime
    fetch_status: FetchStatus
    changed: bool


def normalize_url(url: str) -> str:
    """Return a stable canonical URL for registry matching."""

    parts = urlsplit(url.strip())
    scheme = (parts.scheme or "https").lower()
    netloc = parts.netloc.lower()
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/" and path.endswith("/"):
        path = path[:-1]

    kept_query = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if lowered in TRACKING_PARAMS or any(lowered.startswith(prefix) for prefix in TRACKING_PARAM_PREFIXES):
            continue
        kept_query.append((key, value))
    query = urlencode(sorted(kept_query))

    return urlunsplit((scheme, netloc, path, query, ""))


def content_hash(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def status_from_http(status_code: int) -> FetchStatus:
    if status_code in PARKED_HTTP_STATUSES or status_code == REDIRECT_LOOP_STATUS:
        return FetchStatus.PARKED
    if 200 <= status_code < 300:
        return FetchStatus.VERIFIED
    if status_code >= 500:
        return FetchStatus.FAILED
    return FetchStatus.BLOCKED


def write_snapshot(
    *,
    source_id: str,
    url: str,
    content: bytes,
    snapshot_root: Path,
    previous_hash: str | None = None,
    fetched_at: datetime | None = None,
    fetch_status: FetchStatus = FetchStatus.VERIFIED,
) -> SnapshotRecord:
    """Write content-addressed snapshot bytes and report whether content changed."""

    canonical_url = normalize_url(url)
    digest = content_hash(content)
    timestamp = fetched_at or datetime.now(UTC)
    case_dir = snapshot_root / source_id
    case_dir.mkdir(parents=True, exist_ok=True)
    suffix = _extension_for_url(canonical_url)
    snapshot_path = case_dir / f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}_{digest[:12]}{suffix}"
    if not snapshot_path.exists():
        snapshot_path.write_bytes(content)

    return SnapshotRecord(
        source_id=source_id,
        canonical_url=canonical_url,
        content_hash=digest,
        snapshot_path=str(snapshot_path),
        fetched_at=timestamp,
        fetch_status=fetch_status,
        changed=previous_hash is None or previous_hash != digest,
    )


def _extension_for_url(url: str) -> str:
    path = urlsplit(url).path.lower()
    if path.endswith(".pdf"):
        return ".pdf"
    if path.endswith(".json"):
        return ".json"
    if path.endswith(".txt"):
        return ".txt"
    return ".html"

