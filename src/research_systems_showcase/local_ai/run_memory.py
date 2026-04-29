from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _output_run_dir(repo_root: Path, config: dict[str, Any]) -> Path:
    monitor_config = config.get("monitor", {})
    path_text = str(monitor_config.get("token_artifact_dir") or config.get("outputs_dir", "outputs/local_ai_runs"))
    path = Path(path_text).expanduser()
    return path if path.is_absolute() else repo_root / path


def _created_at(run_dir: Path, request: dict[str, Any]) -> str:
    value = request.get("created_at")
    if value:
        return str(value)
    return datetime.fromtimestamp(run_dir.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")


def _generation_failures(request: dict[str, Any], manifest: dict[str, Any]) -> list[dict[str, str]]:
    attempts = request.get("generation_attempts") or manifest.get("generation_attempts") or []
    if not isinstance(attempts, list):
        return []
    failures: list[dict[str, str]] = []
    for item in attempts:
        if not isinstance(item, dict) or item.get("ok"):
            continue
        failures.append(
            {
                "backend": str(item.get("backend") or "unknown"),
                "error": str(item.get("error") or "generation_failed"),
            }
        )
    return failures


def _source_counts(request: dict[str, Any]) -> tuple[int, int]:
    source_manifest = request.get("source_manifest", [])
    if not isinstance(source_manifest, list):
        return 0, 0
    total = len(source_manifest)
    included = sum(1 for item in source_manifest if isinstance(item, dict) and item.get("included"))
    return total, included


def _summarize_run(run_dir: Path) -> dict[str, Any]:
    request = _load_json_object(run_dir / "request.json")
    manifest = _load_json_object(run_dir / "manifest.json")
    review_gate = _load_json_object(run_dir / "review_gate.json")
    backend_status = request.get("backend_status", {})
    backend_status = backend_status if isinstance(backend_status, dict) else {}
    source_total, source_included = _source_counts(request)
    failed_checks = review_gate.get("failed_checks", [])
    if not isinstance(failed_checks, list):
        failed_checks = []

    run_id = str(request.get("run_id") or manifest.get("run_id") or run_dir.name)
    mode = str(request.get("mode") or manifest.get("mode") or ("literature_ideation" if run_id.startswith("ideation_") else "research_prompt"))
    generation_error = str(
        review_gate.get("generation_error")
        or manifest.get("generation_error")
        or request.get("generation_error")
        or ""
    )
    generation_failures = _generation_failures(request, manifest)
    if generation_failures and not generation_error:
        generation_error = generation_failures[0]["error"]

    return {
        "run_id": run_id,
        "mode": mode,
        "created_at": _created_at(run_dir, request),
        "prompt": str(request.get("prompt") or request.get("focus") or ""),
        "backend": str(manifest.get("backend") or request.get("backend") or ""),
        "effective_model": str(backend_status.get("effective_model") or ""),
        "fallback_used": bool(manifest.get("fallback_used") or request.get("fallback_used")),
        "decision": str(review_gate.get("decision") or manifest.get("decision") or "unknown"),
        "review_required": bool(review_gate.get("review_required", manifest.get("review_required", True))),
        "can_export_final": bool(review_gate.get("can_export_final", manifest.get("can_export_final", False))),
        "failed_checks": [str(item) for item in failed_checks],
        "generation_error": generation_error,
        "generation_failures": generation_failures,
        "source_count": source_total,
        "included_source_count": source_included,
        "artifacts": manifest.get("artifacts", {}) if isinstance(manifest.get("artifacts"), dict) else {},
        "path": str(run_dir),
    }


def collect_run_memory(repo_root: Path, config: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    run_root = _output_run_dir(repo_root, config)
    run_dirs = []
    if run_root.exists():
        run_dirs = sorted(
            [path for path in run_root.iterdir() if path.is_dir()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    recent_runs = [_summarize_run(path) for path in run_dirs[: max(0, int(limit))]]
    failed_check_counter: Counter[str] = Counter()
    backend_counter: Counter[str] = Counter()
    decision_counter: Counter[str] = Counter()
    mode_counter: Counter[str] = Counter()
    generation_failure_counter: Counter[str] = Counter()

    for item in recent_runs:
        backend_counter.update([item["backend"] or "unknown"])
        decision_counter.update([item["decision"] or "unknown"])
        mode_counter.update([item["mode"] or "unknown"])
        failed_check_counter.update(item.get("failed_checks", []))
        generation_failure_counter.update(failure["backend"] for failure in item.get("generation_failures", []))

    review_queue = [item for item in recent_runs if item.get("review_required") and not item.get("can_export_final")]
    blockers = []
    if failed_check_counter:
        blockers.append("failed_checks: " + ", ".join(f"{name}={count}" for name, count in failed_check_counter.most_common(5)))
    if generation_failure_counter:
        blockers.append(
            "generation_failures: "
            + ", ".join(f"{name}={count}" for name, count in generation_failure_counter.most_common(5))
        )

    return {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_root": str(run_root),
        "total_run_dirs": len(run_dirs),
        "runs_counted": len(recent_runs),
        "counts": {
            "review_required": sum(1 for item in recent_runs if item.get("review_required")),
            "can_export_final": sum(1 for item in recent_runs if item.get("can_export_final")),
            "fallback_used": sum(1 for item in recent_runs if item.get("fallback_used")),
            "generation_errors": sum(1 for item in recent_runs if item.get("generation_error")),
            "decisions": dict(decision_counter),
            "backends": dict(backend_counter),
            "modes": dict(mode_counter),
            "failed_checks": dict(failed_check_counter),
        },
        "review_queue": review_queue,
        "recent_runs": recent_runs,
        "blockers": blockers,
        "policy": "Run memory is read-only inspection state. It never approves, finalizes, or exports model outputs.",
    }


def render_run_memory_summary(memory: dict[str, Any]) -> str:
    counts = memory.get("counts", {})
    lines = [
        "Local Run Memory",
        "",
        f"Run root: {memory.get('run_root', '')}",
        f"Run directories found: {memory.get('total_run_dirs', 0)}",
        f"Runs counted: {memory.get('runs_counted', 0)}",
        f"Review required: {counts.get('review_required', 0)}",
        f"Can export final: {counts.get('can_export_final', 0)}",
        f"Fallback used: {counts.get('fallback_used', 0)}",
        f"Generation errors/failures: {counts.get('generation_errors', 0)}",
        "",
    ]
    blockers = memory.get("blockers", [])
    if blockers:
        lines.append("Current bottlenecks:")
        lines.extend(f"- {item}" for item in blockers)
        lines.append("")

    recent_runs = memory.get("recent_runs", [])
    if recent_runs:
        lines.append("Recent runs:")
        for item in recent_runs:
            checks = ", ".join(item.get("failed_checks", [])) or "none"
            model = item.get("effective_model") or "unknown model"
            lines.append(
                "- {run_id} | {mode} | {backend}/{model} | decision={decision} | "
                "review_required={review_required} | failed_checks={checks}".format(
                    run_id=item.get("run_id", "unknown"),
                    mode=item.get("mode", "unknown"),
                    backend=item.get("backend", "unknown"),
                    model=model,
                    decision=item.get("decision", "unknown"),
                    review_required=item.get("review_required", True),
                    checks=checks,
                )
            )
            if item.get("generation_error"):
                lines.append(f"  generation_error: {item['generation_error'][:180]}")
            lines.append(f"  path: {item.get('path', '')}")
    else:
        lines.append("Recent runs: none")

    lines.extend(["", str(memory.get("policy", ""))])
    return "\n".join(lines)


def write_run_memory_snapshot(
    memory: dict[str, Any],
    repo_root: Path,
    config: dict[str, Any],
    output_dir: Path | None = None,
) -> Path:
    monitor_config = config.get("monitor", {})
    default_dir = repo_root / str(monitor_config.get("outputs_dir", "outputs/system_monitor"))
    target_dir = output_dir or default_dir
    output_path = ensure_directory(target_dir) / f"run_memory_{_utc_stamp()}.json"
    write_json(output_path, memory)
    return output_path
