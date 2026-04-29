from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import mimetypes
from pathlib import Path
import re
import shutil
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from ..utils.io import ensure_directory, write_json, write_text
from .assistant import _read_source_text


DEFAULT_MAX_BYTES = 10_000_000
DEFAULT_TIMEOUT_SECONDS = 30
DEFAULT_TEXT_CHAR_LIMIT = 200_000
ALLOWED_SCHEMES = {"http", "https"}


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_name(value: str, fallback: str = "source") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())[:120].strip("._-")
    return cleaned or fallback


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _unique_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 10_000):
        next_candidate = folder / f"{stem}_{index}{suffix}"
        if not next_candidate.exists():
            return next_candidate
    raise RuntimeError(f"Could not allocate a unique filename for {filename}")


def _read_url_file(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("#")]


def _filename_from_url(url: str, content_type: str) -> str:
    parsed = urlparse(url)
    name = Path(parsed.path).name
    if not name:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]
        extension = mimetypes.guess_extension(content_type.split(";")[0].strip()) or ".bin"
        name = f"remote_{digest}{extension}"
    return _safe_name(name, fallback="remote_source.bin")


def _read_capped_response(url: str, timeout_seconds: int, max_bytes: int) -> tuple[bytes, str, int]:
    request = Request(
        url,
        headers={
            "User-Agent": "review-gated-research-systems/0.1 local-data-intake",
            "Accept": "*/*",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(min(65536, max_bytes + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > max_bytes:
                raise ValueError(f"response_exceeds_max_bytes:{max_bytes}")
        content_type = str(response.headers.get("Content-Type", "application/octet-stream"))
        status = int(getattr(response, "status", 200))
    return b"".join(chunks), content_type, status


def _extract_text_artifact(raw_path: Path, text_dir: Path, text_char_limit: int) -> dict[str, Any]:
    text, reason = _read_source_text(raw_path)
    if reason:
        return {
            "text_extracted": False,
            "extraction_reason": reason,
            "extracted_text_path": "",
            "extracted_text_characters": 0,
            "extracted_text_truncated": False,
        }
    truncated = len(text) > text_char_limit
    output_path = _unique_path(text_dir, f"{raw_path.stem}.txt")
    write_text(output_path, text[:text_char_limit] + ("\n" if text else ""))
    return {
        "text_extracted": True,
        "extraction_reason": "",
        "extracted_text_path": str(output_path),
        "extracted_text_characters": min(len(text), text_char_limit),
        "extracted_text_truncated": truncated,
    }


def _acquire_url(
    url: str,
    raw_dir: Path,
    text_dir: Path,
    timeout_seconds: int,
    max_bytes: int,
    text_char_limit: int,
    dry_run: bool,
) -> dict[str, Any]:
    parsed = urlparse(url)
    record: dict[str, Any] = {
        "source_type": "url",
        "source": url,
        "status": "pending",
        "raw_path": "",
        "bytes": 0,
        "sha256": "",
        "content_type": "",
        "http_status": "",
        "error": "",
    }
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        record.update({"status": "skipped", "error": "unsupported_url_scheme"})
        return record
    if dry_run:
        record.update({"status": "dry_run"})
        return record
    try:
        payload, content_type, http_status = _read_capped_response(url, timeout_seconds, max_bytes)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError) as exc:
        record.update({"status": "failed", "error": f"{type(exc).__name__}: {exc}"})
        return record

    filename = _filename_from_url(url, content_type)
    raw_path = _unique_path(raw_dir, filename)
    raw_path.write_bytes(payload)
    record.update(
        {
            "status": "acquired",
            "raw_path": str(raw_path),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
            "content_type": content_type,
            "http_status": http_status,
        }
    )
    record.update(_extract_text_artifact(raw_path, text_dir, text_char_limit))
    return record


def _acquire_local_file(
    source_path: Path,
    raw_dir: Path,
    text_dir: Path,
    text_char_limit: int,
    dry_run: bool,
) -> dict[str, Any]:
    source_path = source_path.expanduser()
    record: dict[str, Any] = {
        "source_type": "local_file",
        "source": str(source_path),
        "status": "pending",
        "raw_path": "",
        "bytes": 0,
        "sha256": "",
        "content_type": "",
        "http_status": "",
        "error": "",
    }
    if not source_path.exists():
        record.update({"status": "failed", "error": "source_path_missing"})
        return record
    if not source_path.is_file():
        record.update({"status": "failed", "error": "source_path_not_file"})
        return record
    if dry_run:
        record.update({"status": "dry_run"})
        return record
    payload = source_path.read_bytes()
    raw_path = _unique_path(raw_dir, _safe_name(source_path.name, fallback="local_source"))
    shutil.copy2(source_path, raw_path)
    record.update(
        {
            "status": "acquired",
            "raw_path": str(raw_path),
            "bytes": len(payload),
            "sha256": _sha256_bytes(payload),
            "content_type": mimetypes.guess_type(str(source_path))[0] or "",
        }
    )
    record.update(_extract_text_artifact(raw_path, text_dir, text_char_limit))
    return record


def acquire_data_sources(
    repo_root: Path,
    config: dict[str, Any],
    urls: list[str] | None = None,
    url_file: Path | None = None,
    local_sources: list[Path] | None = None,
    output_dir: Path | None = None,
    max_bytes: int | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    acquisition_config = config.get("data_acquisition", {})
    base_output = output_dir or repo_root / str(acquisition_config.get("outputs_dir", "outputs/data_intake"))
    run_dir = ensure_directory(base_output / f"data_intake_{_utc_stamp()}")
    raw_dir = ensure_directory(run_dir / "raw")
    text_dir = ensure_directory(run_dir / "extracted_text")
    timeout_seconds = int(acquisition_config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS))
    max_bytes_value = int(max_bytes or acquisition_config.get("max_bytes_per_source", DEFAULT_MAX_BYTES))
    text_char_limit = int(acquisition_config.get("extracted_text_char_limit", DEFAULT_TEXT_CHAR_LIMIT))

    all_urls = list(urls or [])
    if url_file is not None:
        all_urls.extend(_read_url_file(url_file))
    records = [
        _acquire_url(
            url=url,
            raw_dir=raw_dir,
            text_dir=text_dir,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes_value,
            text_char_limit=text_char_limit,
            dry_run=dry_run,
        )
        for url in all_urls
    ]
    records.extend(
        _acquire_local_file(
            source_path=path,
            raw_dir=raw_dir,
            text_dir=text_dir,
            text_char_limit=text_char_limit,
            dry_run=dry_run,
        )
        for path in (local_sources or [])
    )

    counts = {
        "requested": len(records),
        "acquired": sum(1 for item in records if item.get("status") == "acquired"),
        "failed": sum(1 for item in records if item.get("status") == "failed"),
        "skipped": sum(1 for item in records if item.get("status") == "skipped"),
        "dry_run": sum(1 for item in records if item.get("status") == "dry_run"),
        "text_extracted": sum(1 for item in records if item.get("text_extracted")),
    }
    manifest = {
        "run_id": run_dir.name,
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_dir": str(run_dir),
        "raw_dir": str(raw_dir),
        "extracted_text_dir": str(text_dir),
        "max_bytes_per_source": max_bytes_value,
        "dry_run": dry_run,
        "counts": counts,
        "records": records,
        "policy": (
            "Data acquisition is limited to user-supplied URLs and local files. "
            "It writes traceable artifacts and does not approve, analyze, or export final research outputs."
        ),
    }
    manifest_path = run_dir / "intake_manifest.json"
    write_json(manifest_path, manifest)
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def render_data_acquisition_summary(manifest: dict[str, Any]) -> str:
    counts = manifest.get("counts", {})
    lines = [
        "Local Data Acquisition",
        "",
        f"Run directory: {manifest.get('run_dir', '')}",
        f"Manifest: {manifest.get('manifest_path', '')}",
        f"Requested: {counts.get('requested', 0)}",
        f"Acquired: {counts.get('acquired', 0)}",
        f"Text extracted: {counts.get('text_extracted', 0)}",
        f"Failed: {counts.get('failed', 0)}",
        f"Skipped: {counts.get('skipped', 0)}",
        f"Dry run: {counts.get('dry_run', 0)}",
        "",
        "Records:",
    ]
    records = manifest.get("records", [])
    if not records:
        lines.append("- none")
    for item in records:
        lines.append(
            "- {status} | {source_type} | {source} | bytes={bytes} | text_extracted={text}".format(
                status=item.get("status", "unknown"),
                source_type=item.get("source_type", "unknown"),
                source=item.get("source", ""),
                bytes=item.get("bytes", 0),
                text=item.get("text_extracted", False),
            )
        )
        if item.get("raw_path"):
            lines.append(f"  raw: {item['raw_path']}")
        if item.get("extracted_text_path"):
            lines.append(f"  text: {item['extracted_text_path']}")
        if item.get("error"):
            lines.append(f"  error: {item['error']}")
    lines.extend(["", str(manifest.get("policy", ""))])
    return "\n".join(lines)
