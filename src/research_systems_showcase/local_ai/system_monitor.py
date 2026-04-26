from __future__ import annotations

import json
import math
import os
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json
from .backends import collect_backend_statuses


APPROX_CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / APPROX_CHARS_PER_TOKEN))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_run(command: list[str], timeout: float = 3.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    output = (result.stdout or result.stderr or "").strip()
    return result.returncode == 0, output


def collect_cpu_snapshot() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1
    try:
        load_1, load_5, load_15 = os.getloadavg()
    except OSError:
        load_1 = load_5 = load_15 = 0.0
    return {
        "cpu_count": cpu_count,
        "load_average": {
            "1m": round(load_1, 2),
            "5m": round(load_5, 2),
            "15m": round(load_15, 2),
        },
        "load_ratio_1m": round(load_1 / cpu_count, 3),
        "note": "Load ratio is load average divided by logical CPU count.",
    }


def _parse_vm_stat(output: str) -> dict[str, Any]:
    page_size = 4096
    stats: dict[str, int] = {}
    for line in output.splitlines():
        line = line.strip()
        if "page size of" in line:
            parts = [part for part in line.split() if part.isdigit()]
            if parts:
                page_size = int(parts[0])
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        digits = "".join(character for character in value if character.isdigit())
        if digits:
            stats[key.strip(".").casefold().replace(" ", "_")] = int(digits)

    free_pages = (
        stats.get("pages_free", 0)
        + stats.get("pages_inactive", 0)
        + stats.get("pages_speculative", 0)
    )
    active_pages = stats.get("pages_active", 0) + stats.get("pages_wired_down", 0)
    compressed_pages = stats.get("pages_occupied_by_compressor", 0)
    total_known_pages = free_pages + active_pages + compressed_pages
    free_bytes = free_pages * page_size
    active_bytes = active_pages * page_size
    compressed_bytes = compressed_pages * page_size
    return {
        "source": "vm_stat",
        "page_size": page_size,
        "free_or_inactive_bytes": free_bytes,
        "active_or_wired_bytes": active_bytes,
        "compressed_bytes": compressed_bytes,
        "known_total_bytes": total_known_pages * page_size,
        "free_or_inactive_gb": round(free_bytes / (1024**3), 2),
        "active_or_wired_gb": round(active_bytes / (1024**3), 2),
        "compressed_gb": round(compressed_bytes / (1024**3), 2),
    }


def collect_memory_snapshot() -> dict[str, Any]:
    if platform.system() == "Darwin":
        ok, output = _safe_run(["vm_stat"])
        if ok:
            return _parse_vm_stat(output)
        return {"source": "vm_stat", "status": "unavailable", "detail": output}

    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        values: dict[str, int] = {}
        for line in meminfo.read_text(encoding="utf-8", errors="replace").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            digits = "".join(character for character in value if character.isdigit())
            if digits:
                values[key] = int(digits) * 1024
        total = values.get("MemTotal", 0)
        available = values.get("MemAvailable", 0)
        return {
            "source": "/proc/meminfo",
            "total_gb": round(total / (1024**3), 2) if total else None,
            "available_gb": round(available / (1024**3), 2) if available else None,
            "available_fraction": round(available / total, 3) if total else None,
        }

    return {"source": "unknown", "status": "unavailable"}


def _resolve_monitor_path(repo_root: Path, path_text: str) -> Path:
    path = Path(path_text).expanduser()
    if path.is_absolute():
        return path
    return repo_root / path


def collect_disk_snapshot(repo_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    monitor_config = config.get("monitor", {})
    configured_paths = monitor_config.get("disk_paths") or [
        ".",
        str(config.get("outputs_dir", "outputs/local_ai_runs")),
        "/tmp",
    ]
    records: list[dict[str, Any]] = []
    for path_text in configured_paths:
        path = _resolve_monitor_path(repo_root, str(path_text))
        target = path
        while not target.exists() and target != target.parent:
            target = target.parent
        try:
            usage = shutil.disk_usage(target)
        except OSError as exc:
            records.append(
                {
                    "path": str(path),
                    "status": "unavailable",
                    "detail": f"{type(exc).__name__}: {exc}",
                }
            )
            continue
        free_fraction = usage.free / usage.total if usage.total else 0.0
        records.append(
            {
                "path": str(path),
                "target_checked": str(target),
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "free_fraction": round(free_fraction, 3),
            }
        )
    return records


def collect_thermal_snapshot() -> dict[str, Any]:
    if platform.system() != "Darwin":
        return {
            "temperature_celsius": None,
            "thermal_pressure": "unavailable",
            "detail": "Portable non-privileged temperature probe is not available on this platform.",
        }

    ok, output = _safe_run(["pmset", "-g", "therm"])
    if ok and "Error:" not in output:
        pressure = "nominal" if "No thermal warning" in output else output or "available_no_detail"
        return {
            "temperature_celsius": None,
            "thermal_pressure": pressure,
            "detail": (
                "macOS does not expose precise CPU/GPU temperature through a stable "
                "non-privileged standard-library API."
            ),
        }
    return {
        "temperature_celsius": None,
        "thermal_pressure": "unavailable",
        "detail": output or "pmset thermal probe returned no usable data.",
    }


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _iter_run_dirs(base_dir: Path) -> list[Path]:
    if not base_dir.exists():
        return []
    return sorted(
        [path for path in base_dir.iterdir() if path.is_dir()],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def collect_token_snapshot(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    monitor_config = config.get("monitor", {})
    outputs_dir = _resolve_monitor_path(
        repo_root,
        str(monitor_config.get("token_artifact_dir") or config.get("outputs_dir", "outputs/local_ai_runs")),
    )
    max_runs = int(monitor_config.get("token_recent_run_limit", 20))
    run_records: list[dict[str, Any]] = []
    total_source_tokens = 0
    total_prompt_tokens = 0
    total_output_tokens = 0

    for run_dir in _iter_run_dirs(outputs_dir)[:max_runs]:
        request = _load_json(run_dir / "request.json")
        if not request:
            continue
        prompt_text = str(request.get("prompt") or request.get("focus") or "")
        source_chars = int(request.get("source_context_characters") or 0)
        output_text = ""
        for output_name in ("draft_response.md", "idea_brief.md"):
            output_path = run_dir / output_name
            if output_path.exists():
                try:
                    output_text += output_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    pass

        source_tokens = math.ceil(source_chars / APPROX_CHARS_PER_TOKEN) if source_chars else 0
        prompt_tokens = estimate_tokens(prompt_text)
        output_tokens = estimate_tokens(output_text)
        total_source_tokens += source_tokens
        total_prompt_tokens += prompt_tokens
        total_output_tokens += output_tokens
        run_records.append(
            {
                "run_id": request.get("run_id") or run_dir.name,
                "created_at": request.get("created_at", ""),
                "backend": request.get("backend", ""),
                "fallback_used": bool(request.get("fallback_used", False)),
                "estimated_prompt_tokens": prompt_tokens,
                "estimated_source_tokens": source_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_total_tokens": prompt_tokens + source_tokens + output_tokens,
            }
        )

    return {
        "source": str(outputs_dir),
        "estimation_note": (
            "Token counts are local estimates based on stored artifacts. They do not include "
            "Codex/ChatGPT UI tokens or provider-side hidden reasoning tokens."
        ),
        "runs_counted": len(run_records),
        "estimated_prompt_tokens": total_prompt_tokens,
        "estimated_source_tokens": total_source_tokens,
        "estimated_output_tokens": total_output_tokens,
        "estimated_total_tokens": total_prompt_tokens + total_source_tokens + total_output_tokens,
        "recent_runs": run_records,
    }


def build_model_routing_advice(
    statuses: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    primary = str(config.get("primary_backend", "ollama")).lower()
    review = str(config.get("review_backend", "lmstudio")).lower()
    candidates: list[dict[str, Any]] = []
    advisories: list[str] = []

    for backend_name in (primary, review, "ollama", "lmstudio"):
        if backend_name in {candidate["backend"] for candidate in candidates}:
            continue
        status = statuses.get(backend_name)
        if not status:
            continue
        candidates.append(
            {
                "backend": backend_name,
                "configured_model": status.get("configured_model", ""),
                "effective_model": status.get("effective_model", ""),
                "available_models": status.get("available_models", []),
                "status_label": status.get("status_label", "unknown"),
            }
        )

    primary_status = statuses.get(primary, {})
    review_status = statuses.get(review, {})
    if not primary_status.get("reachable"):
        advisories.append(f"Primary backend '{primary}' is not reachable; use dry-run or fallback.")
    elif primary_status.get("configured_model") and not primary_status.get("effective_model"):
        advisories.append(f"Primary backend '{primary}' has no available configured model.")

    if bool(config.get("fallback_to_review_backend", False)) and review_status.get("reachable"):
        advisories.append(f"Review backend '{review}' is available as a fallback path.")
    elif bool(config.get("fallback_to_review_backend", False)):
        advisories.append(f"Review backend '{review}' fallback is configured but unavailable.")

    if not advisories:
        advisories.append("Configured model path is available. Keep outputs review-gated.")

    return {
        "primary_backend": primary,
        "review_backend": review,
        "fallback_to_review_backend": bool(config.get("fallback_to_review_backend", False)),
        "candidates": candidates,
        "advisories": advisories,
        "policy": (
            "Model switching changes draft-generation behavior only. It does not bypass "
            "validation, review gates, or human approval."
        ),
    }


def _status_from_thresholds(snapshot: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    monitor_config = config.get("monitor", {})
    high_load_ratio = float(monitor_config.get("high_load_ratio", 0.85))
    low_disk_free_fraction = float(monitor_config.get("low_disk_free_fraction", 0.1))
    advisories: list[str] = []

    load_ratio = float(snapshot.get("cpu", {}).get("load_ratio_1m") or 0.0)
    if load_ratio >= high_load_ratio:
        advisories.append("CPU load is high. Prefer shorter prompts or pause batch work.")

    for disk in snapshot.get("disk", []):
        free_fraction = disk.get("free_fraction")
        if isinstance(free_fraction, (int, float)) and free_fraction <= low_disk_free_fraction:
            advisories.append(f"Low disk free space near {disk.get('path')}. Avoid large artifact runs.")

    if snapshot.get("thermal", {}).get("thermal_pressure") in {"Warning", "Critical"}:
        advisories.append("Thermal pressure is elevated. Pause long model runs until cooling improves.")

    return {
        "status": "attention" if advisories else "ok",
        "advisories": advisories,
    }


def collect_monitor_snapshot(repo_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    backend_statuses = collect_backend_statuses(config)
    snapshot: dict[str, Any] = {
        "created_at": _utc_now(),
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "cpu": collect_cpu_snapshot(),
        "memory": collect_memory_snapshot(),
        "disk": collect_disk_snapshot(repo_root, config),
        "thermal": collect_thermal_snapshot(),
        "token_usage": collect_token_snapshot(repo_root, config),
        "backends": backend_statuses,
        "model_routing": build_model_routing_advice(backend_statuses, config),
        "control_policy": {
            "local_only": True,
            "auto_actions_enabled": False,
            "note": "This monitor reports status only. It does not start, stop, or finalize research work.",
        },
    }
    snapshot["summary"] = _status_from_thresholds(snapshot, config)
    return snapshot


def render_model_summary(model_routing: dict[str, Any]) -> str:
    lines = [
        "Model Routing Status",
        f"- Primary backend: {model_routing.get('primary_backend', '')}",
        f"- Review backend: {model_routing.get('review_backend', '')}",
        f"- Fallback enabled: {model_routing.get('fallback_to_review_backend', False)}",
    ]
    for candidate in model_routing.get("candidates", []):
        available = ", ".join(candidate.get("available_models", [])) or "none"
        lines.append(
            f"- {candidate.get('backend')}: {candidate.get('status_label')} | "
            f"configured={candidate.get('configured_model') or 'none'} | "
            f"effective={candidate.get('effective_model') or 'none'} | "
            f"available={available}"
        )
    for advisory in model_routing.get("advisories", []):
        lines.append(f"- Advice: {advisory}")
    lines.append(f"- Policy: {model_routing.get('policy', '')}")
    return "\n".join(lines)


def render_monitor_summary(snapshot: dict[str, Any]) -> str:
    cpu = snapshot.get("cpu", {})
    memory = snapshot.get("memory", {})
    token_usage = snapshot.get("token_usage", {})
    thermal = snapshot.get("thermal", {})
    summary = snapshot.get("summary", {})
    backends = snapshot.get("backends", {})

    lines = [
        "Local Research AI Monitor",
        f"- Overall status: {summary.get('status', 'unknown')}",
        f"- Timestamp: {snapshot.get('created_at', '')}",
        f"- CPU load: {cpu.get('load_average', {}).get('1m', 'n/a')} "
        f"on {cpu.get('cpu_count', 'n/a')} logical CPUs "
        f"(ratio {cpu.get('load_ratio_1m', 'n/a')})",
    ]
    if memory.get("available_gb") is not None:
        lines.append(f"- Memory available: {memory.get('available_gb')} GB")
    elif memory.get("free_or_inactive_gb") is not None:
        lines.append(
            "- Memory free/inactive: "
            f"{memory.get('free_or_inactive_gb')} GB; active/wired: {memory.get('active_or_wired_gb')} GB"
        )
    else:
        lines.append(f"- Memory: {memory.get('status', 'unavailable')}")

    lines.append(f"- Thermal: {thermal.get('thermal_pressure', 'unavailable')}")
    lines.append(
        "- Estimated local artifact tokens: "
        f"{token_usage.get('estimated_total_tokens', 0)} "
        f"across {token_usage.get('runs_counted', 0)} recent runs"
    )
    for name, status in backends.items():
        lines.append(
            f"- {name}: {status.get('status_label', 'unknown')} "
            f"(effective model: {status.get('effective_model') or 'none'})"
        )
    for disk in snapshot.get("disk", []):
        lines.append(
            f"- Disk {disk.get('path')}: {disk.get('free_gb', 'n/a')} GB free "
            f"({disk.get('free_fraction', 'n/a')})"
        )
    advisories = summary.get("advisories") or []
    if advisories:
        lines.append("Advisories:")
        lines.extend(f"- {advisory}" for advisory in advisories)
    else:
        lines.append("Advisories: none")
    lines.append("")
    lines.append(render_model_summary(snapshot.get("model_routing", {})))
    return "\n".join(lines)


def write_monitor_snapshot(
    snapshot: dict[str, Any],
    repo_root: Path,
    config: dict[str, Any],
    output_dir: Path | None = None,
) -> Path:
    monitor_config = config.get("monitor", {})
    base_dir = output_dir or _resolve_monitor_path(
        repo_root,
        str(monitor_config.get("outputs_dir") or "outputs/system_monitor"),
    )
    ensure_directory(base_dir)
    path = base_dir / f"monitor_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    write_json(path, snapshot)
    return path
