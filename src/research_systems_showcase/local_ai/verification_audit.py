from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..utils.io import ensure_directory, write_json, write_text
from .run_memory import collect_run_memory
from .workflow_templates import WORKFLOW_TEMPLATES


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _risk_level(flags: list[str]) -> str:
    high_risk = {
        "generation_error_present",
        "no_source_included",
        "review_required",
        "high_stakes_template_fields_require_review",
    }
    if any(flag in high_risk for flag in flags):
        return "high"
    if flags:
        return "medium"
    return "low"


def _audit_run(run: dict[str, Any], template_id: str | None) -> dict[str, Any]:
    flags: list[str] = []
    if run.get("review_required"):
        flags.append("review_required")
    if not run.get("can_export_final"):
        flags.append("not_exportable")
    if run.get("generation_error"):
        flags.append("generation_error_present")
    if run.get("fallback_used"):
        flags.append("fallback_used")
    if int(run.get("included_source_count", 0)) == 0:
        flags.append("no_source_included")
    flags.extend(f"failed_check:{item}" for item in run.get("failed_checks", []))

    template_note = ""
    if template_id:
        template = WORKFLOW_TEMPLATES.get(template_id)
        if template:
            flags.append("high_stakes_template_fields_require_review")
            template_note = (
                "Template high-stakes fields require human review before final use: "
                + ", ".join(template.get("high_stakes_fields", []))
            )

    escalation = "human_review" if run.get("review_required") or flags else "monitor"
    if run.get("generation_error") or int(run.get("included_source_count", 0)) == 0:
        escalation = "repair_or_rerun_before_review"

    return {
        "run_id": run.get("run_id", "unknown"),
        "mode": run.get("mode", "unknown"),
        "backend": run.get("backend", ""),
        "effective_model": run.get("effective_model", ""),
        "decision": run.get("decision", "unknown"),
        "review_required": bool(run.get("review_required", True)),
        "can_export_final": bool(run.get("can_export_final", False)),
        "risk_level": _risk_level(flags),
        "escalation": escalation,
        "flags": flags,
        "template_note": template_note,
        "generation_error": run.get("generation_error", ""),
        "path": run.get("path", ""),
    }


def build_verification_audit(
    repo_root: Path,
    config: dict[str, Any],
    template_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    normalized_template = template_id.strip().casefold() if template_id else None
    if normalized_template and normalized_template not in WORKFLOW_TEMPLATES:
        available = ", ".join(sorted(WORKFLOW_TEMPLATES))
        raise ValueError(f"Unknown workflow template '{template_id}'. Available templates: {available}.")

    memory = collect_run_memory(repo_root, config, limit=limit)
    audited_runs = [_audit_run(run, normalized_template) for run in memory.get("recent_runs", [])]
    flag_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    escalation_counter: Counter[str] = Counter()
    for item in audited_runs:
        flag_counter.update(item.get("flags", []))
        risk_counter.update([item.get("risk_level", "unknown")])
        escalation_counter.update([item.get("escalation", "unknown")])

    recommended_actions: list[str] = []
    if flag_counter.get("generation_error_present", 0):
        recommended_actions.append("repair or switch the failing generation backend before scaling batch work")
    if any(flag.startswith("failed_check:final_answer_present") for flag in flag_counter):
        recommended_actions.append("fix reasoning-only or empty final-answer outputs before relying on draft generation")
    if flag_counter.get("no_source_included", 0):
        recommended_actions.append("repair source intake/extraction before model processing")
    if not recommended_actions and audited_runs:
        recommended_actions.append("sample human review is still required before downstream use")
    if not audited_runs:
        recommended_actions.append("run acquire, ask, or ideate first so audit has artifacts to inspect")

    return {
        "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "template_id": normalized_template or "",
        "runs_audited": len(audited_runs),
        "counts": {
            "risk_levels": dict(risk_counter),
            "escalations": dict(escalation_counter),
            "flags": dict(flag_counter),
        },
        "recommended_actions": recommended_actions,
        "audited_runs": audited_runs,
        "policy": (
            "Verification audit is a triage layer. It can flag, escalate, or recommend reruns, "
            "but it cannot approve final research claims."
        ),
    }


def render_verification_audit_summary(audit: dict[str, Any]) -> str:
    lines = [
        "Verification Audit",
        "",
        f"Template: {audit.get('template_id') or 'none'}",
        f"Runs audited: {audit.get('runs_audited', 0)}",
        "",
        "Recommended actions:",
    ]
    lines.extend(f"- {item}" for item in audit.get("recommended_actions", []))
    counts = audit.get("counts", {})
    if counts:
        lines.extend(["", "Counts:"])
        for name, payload in counts.items():
            lines.append(f"- {name}: {payload}")
    audited_runs = audit.get("audited_runs", [])
    lines.extend(["", "Audited runs:"])
    if not audited_runs:
        lines.append("- none")
    for item in audited_runs:
        lines.append(
            "- {run_id} | risk={risk} | escalation={escalation} | decision={decision} | flags={flags}".format(
                run_id=item.get("run_id", "unknown"),
                risk=item.get("risk_level", "unknown"),
                escalation=item.get("escalation", "unknown"),
                decision=item.get("decision", "unknown"),
                flags=", ".join(item.get("flags", [])) or "none",
            )
        )
        if item.get("generation_error"):
            lines.append(f"  generation_error: {item['generation_error'][:180]}")
        if item.get("template_note"):
            lines.append(f"  template_note: {item['template_note']}")
    lines.extend(["", str(audit.get("policy", ""))])
    return "\n".join(lines)


def write_verification_audit(
    audit: dict[str, Any],
    repo_root: Path,
    output_dir: Path | None = None,
) -> dict[str, str]:
    base_dir = output_dir or repo_root / "outputs" / "verification_audits"
    run_dir = ensure_directory(base_dir / f"audit_{_utc_stamp()}")
    json_path = run_dir / "verification_audit.json"
    markdown_path = run_dir / "verification_audit.md"
    write_json(json_path, audit)
    write_text(markdown_path, render_verification_audit_summary(audit) + "\n")
    return {"audit_json": str(json_path), "audit_markdown": str(markdown_path)}
