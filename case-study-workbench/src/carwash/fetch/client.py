from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from carwash.schemas import FetchStatus
from carwash.source_registry import SnapshotRecord, normalize_url, status_from_http, write_snapshot


@dataclass(frozen=True)
class FetchResult:
    canonical_url: str
    status_code: int | None
    fetch_status: FetchStatus
    content: bytes
    fetched_at: datetime
    final_url: str | None = None
    error: str | None = None
    attempts: int = 1


@dataclass(frozen=True)
class FetchSnapshotResult:
    fetch: FetchResult
    snapshot: SnapshotRecord | None


async def fetch_url(
    url: str,
    *,
    client: httpx.AsyncClient | None = None,
    max_attempts: int = 3,
    timeout_seconds: float = 20.0,
) -> FetchResult:
    """Fetch one URL with conservative retry/status handling.

    `client` is injectable so tests and future scheduled jobs can control
    transports, authentication, and institutional network policy.
    """

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    canonical_url = normalize_url(url)
    owns_client = client is None
    active_client = client or httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds)
    attempts = 0
    try:
        while attempts < max_attempts:
            attempts += 1
            try:
                response = await active_client.get(canonical_url)
            except httpx.TooManyRedirects as exc:
                return FetchResult(
                    canonical_url=canonical_url,
                    status_code=310,
                    fetch_status=FetchStatus.PARKED,
                    content=b"",
                    fetched_at=datetime.now(UTC),
                    error=str(exc),
                    attempts=attempts,
                )
            except httpx.HTTPError as exc:
                if attempts >= max_attempts:
                    return FetchResult(
                        canonical_url=canonical_url,
                        status_code=None,
                        fetch_status=FetchStatus.FAILED,
                        content=b"",
                        fetched_at=datetime.now(UTC),
                        error=str(exc),
                        attempts=attempts,
                    )
                continue

            fetch_status = status_from_http(response.status_code)
            if fetch_status == FetchStatus.FAILED and attempts < max_attempts:
                continue
            return FetchResult(
                canonical_url=canonical_url,
                status_code=response.status_code,
                fetch_status=fetch_status,
                content=response.content if fetch_status == FetchStatus.VERIFIED else b"",
                fetched_at=datetime.now(UTC),
                final_url=str(response.url),
                attempts=attempts,
            )
    finally:
        if owns_client:
            await active_client.aclose()

    return FetchResult(
        canonical_url=canonical_url,
        status_code=None,
        fetch_status=FetchStatus.FAILED,
        content=b"",
        fetched_at=datetime.now(UTC),
        error="exhausted attempts without response",
        attempts=attempts,
    )


async def fetch_and_snapshot(
    *,
    source_id: str,
    url: str,
    snapshot_root: Path,
    previous_hash: str | None = None,
    client: httpx.AsyncClient | None = None,
    max_attempts: int = 3,
) -> FetchSnapshotResult:
    """Fetch a URL and snapshot only verified content."""

    fetch = await fetch_url(url, client=client, max_attempts=max_attempts)
    if fetch.fetch_status != FetchStatus.VERIFIED:
        return FetchSnapshotResult(fetch=fetch, snapshot=None)

    snapshot = write_snapshot(
        source_id=source_id,
        url=fetch.canonical_url,
        content=fetch.content,
        snapshot_root=snapshot_root,
        previous_hash=previous_hash,
        fetched_at=fetch.fetched_at,
        fetch_status=fetch.fetch_status,
    )
    return FetchSnapshotResult(fetch=fetch, snapshot=snapshot)
