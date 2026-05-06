from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json, write_text


def _memory_dir(repo_root: Path, config: dict[str, Any]) -> Path:
    memory_config = config.get("review_memory", {})
    path = Path(str(memory_config.get("dir", "outputs/review_memory"))).expanduser()
    return path if path.is_absolute() else repo_root / path


def _ledger_path(repo_root: Path, config: dict[str, Any]) -> Path:
    return _memory_dir(repo_root, config) / "review_memory.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_review_memory(
    repo_root: Path,
    config: dict[str, Any],
    run_id: str,
    field: str,
    decision: str,
    correction: str = "",
    rationale: str = "",
    reviewer: str = "",
    source_path: str = "",
) -> dict[str, Any]:
    if not run_id.strip():
        raise ValueError("run_id is required.")
    if not field.strip():
        raise ValueError("field is required.")
    if not decision.strip():
        raise ValueError("decision is required.")

    record = {
        "created_at": _utc_now(),
        "run_id": run_id.strip(),
        "field": field.strip(),
        "decision": decision.strip(),
        "correction": correction.strip(),
        "rationale": rationale.strip(),
        "reviewer": reviewer.strip(),
        "source_path": source_path.strip(),
        "policy": "Human-entered review memory is reusable evidence for future review, not automatic approval.",
    }
    ledger = _ledger_path(repo_root, config)
    ensure_directory(ledger.parent)
    with ledger.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def _read_records(ledger: Path) -> list[dict[str, Any]]:
    if not ledger.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def collect_review_memory(repo_root: Path, config: dict[str, Any], limit: int = 20) -> dict[str, Any]:
    ledger = _ledger_path(repo_root, config)
    records = _read_records(ledger)
    field_counter: Counter[str] = Counter()
    decision_counter: Counter[str] = Counter()
    run_counter: Counter[str] = Counter()
    for item in records:
        field_counter.update([str(item.get("field") or "unknown")])
        decision_counter.update([str(item.get("decision") or "unknown")])
        run_counter.update([str(item.get("run_id") or "unknown")])
    recent = list(reversed(records[-max(0, int(limit)) :]))
    return {
        "created_at": _utc_now(),
        "ledger_path": str(ledger),
        "records_total": len(records),
        "recent_records": recent,
        "counts": {
            "fields": dict(field_counter),
            "decisions": dict(decision_counter),
            "runs": dict(run_counter),
        },
        "policy": (
            "Review memory stores human corrections and codebook decisions as local artifacts. "
            "It supports retrieval and calibration but does not remove review gates."
        ),
    }


def render_review_memory_summary(memory: dict[str, Any]) -> str:
    lines = [
        "Local Review Memory",
        "",
        f"Ledger: {memory.get('ledger_path', '')}",
        f"Records total: {memory.get('records_total', 0)}",
        "",
        "Counts:",
    ]
    counts = memory.get("counts", {})
    for name, payload in counts.items():
        lines.append(f"- {name}: {payload}")
    lines.extend(["", "Recent records:"])
    records = memory.get("recent_records", [])
    if not records:
        lines.append("- none")
    for item in records:
        lines.append(
            "- {run_id} | field={field} | decision={decision} | correction={correction}".format(
                run_id=item.get("run_id", "unknown"),
                field=item.get("field", "unknown"),
                decision=item.get("decision", "unknown"),
                correction=item.get("correction", ""),
            )
        )
        if item.get("rationale"):
            lines.append(f"  rationale: {item['rationale']}")
    lines.extend(["", str(memory.get("policy", ""))])
    return "\n".join(lines)


def write_review_memory_summary(
    memory: dict[str, Any],
    repo_root: Path,
    config: dict[str, Any],
    output_dir: Path | None = None,
) -> dict[str, str]:
    base_dir = output_dir or _memory_dir(repo_root, config)
    target_dir = ensure_directory(base_dir)
    json_path = target_dir / "review_memory_summary.json"
    markdown_path = target_dir / "review_memory_summary.md"
    write_json(json_path, memory)
    write_text(markdown_path, render_review_memory_summary(memory) + "\n")
    return {"review_memory_json": str(json_path), "review_memory_markdown": str(markdown_path)}
