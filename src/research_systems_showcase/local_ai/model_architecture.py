from __future__ import annotations

from typing import Any


DEFAULT_BORROWED_PATTERNS = [
    "stateful_workflow",
    "role_separated_generation_review",
    "durable_artifact_memory",
    "failed_branch_preservation",
    "local_observability",
]


def _architecture_config(config: dict[str, Any]) -> dict[str, Any]:
    value = config.get("model_architecture", {})
    return value if isinstance(value, dict) else {}


def _status_for(statuses: dict[str, Any] | None, backend_name: str) -> dict[str, Any]:
    if not statuses:
        return {}
    value = statuses.get(backend_name, {})
    return value if isinstance(value, dict) else {}


def _model_label(status: dict[str, Any], config: dict[str, Any], backend_name: str) -> dict[str, str]:
    backend_config = config.get(backend_name, {})
    configured = str(status.get("configured_model") or backend_config.get("model") or "")
    effective = str(status.get("effective_model") or "")
    available = status.get("available_models", [])
    if isinstance(available, list):
        available_text = ", ".join(str(item) for item in available) or "not checked"
    else:
        available_text = "not checked"
    label = str(status.get("status_label") or "not_checked")
    return {
        "configured_model": configured or "none",
        "effective_model": effective or "none",
        "available_models": available_text,
        "status_label": label,
    }


def build_model_execution_plan(
    config: dict[str, Any],
    task_type: str = "research_draft",
    source_count: int = 0,
    statuses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return a serializable, conservative model-workflow plan.

    This is a local architecture description, not an autonomous framework.
    It makes routing and safety boundaries inspectable before or after a run.
    """

    architecture_config = _architecture_config(config)
    primary_backend = str(config.get("primary_backend", "ollama")).lower()
    review_backend = str(config.get("review_backend", "lmstudio")).lower()
    quality_gate = config.get("quality_gate", {})
    fallback_enabled = bool(config.get("fallback_to_review_backend", False))
    review_required = bool(quality_gate.get("require_human_review", True))
    allow_final_without_review = bool(quality_gate.get("allow_final_without_review", False))
    allow_auto_finalize = bool(architecture_config.get("allow_auto_finalize", False))
    auto_finalize = allow_auto_finalize and allow_final_without_review and not review_required

    primary_status = _status_for(statuses, primary_backend)
    review_status = _status_for(statuses, review_backend)
    primary_model = _model_label(primary_status, config, primary_backend)
    review_model = _model_label(review_status, config, review_backend)
    borrowed_patterns = architecture_config.get("borrowed_patterns", DEFAULT_BORROWED_PATTERNS)
    if not isinstance(borrowed_patterns, list):
        borrowed_patterns = DEFAULT_BORROWED_PATTERNS

    stages = [
        {
            "stage_id": "source_intake",
            "role": "source_reader",
            "backend": "deterministic_local",
            "purpose": "Read only user-selected source files and record source_manifest entries.",
            "review_gate": "preserved",
            "failure_policy": "record missing, binary, unreadable, or unsupported sources instead of silently using them.",
        },
        {
            "stage_id": "draft_generation",
            "role": "primary_drafter",
            "backend": primary_backend,
            "configured_model": primary_model["configured_model"],
            "effective_model": primary_model["effective_model"],
            "backend_status": primary_model["status_label"],
            "purpose": "Generate a draft answer or ideation brief from explicit source context.",
            "fallback_backend": review_backend if fallback_enabled and review_backend != primary_backend else "",
            "failure_policy": "if unavailable, write generation_error and keep output in human review.",
        },
        {
            "stage_id": "review_backend_check",
            "role": "secondary_reviewer_or_fallback",
            "backend": review_backend,
            "configured_model": review_model["configured_model"],
            "effective_model": review_model["effective_model"],
            "backend_status": review_model["status_label"],
            "purpose": "Provide a review/fallback path only when explicitly invoked by policy.",
            "review_gate": "does_not_bypass_human_review",
        },
        {
            "stage_id": "quality_gate",
            "role": "deterministic_validator",
            "backend": "deterministic_local",
            "purpose": "Check source sufficiency, answer structure, backend status, and review requirements.",
            "review_gate": "blocks_final_export_without_approval",
        },
        {
            "stage_id": "artifact_memory",
            "role": "run_memory",
            "backend": "local_filesystem",
            "purpose": "Write request, draft, review_gate, manifest, and failure context as inspectable artifacts.",
            "review_gate": "preserves_failed_branches",
        },
        {
            "stage_id": "human_review",
            "role": "human_reviewer",
            "backend": "human_in_the_loop",
            "purpose": "Approve, revise, reject, or benchmark outputs before downstream use.",
            "review_gate": "required_for_final_use",
        },
    ]

    return {
        "architecture_mode": str(architecture_config.get("mode", "review_gated_local")),
        "task_type": task_type,
        "source_count": int(source_count),
        "primary_backend": primary_backend,
        "review_backend": review_backend,
        "fallback_enabled": fallback_enabled,
        "auto_finalize_enabled": auto_finalize,
        "review_required_by_policy": review_required,
        "primary_model": primary_model,
        "review_model": review_model,
        "borrowed_patterns": [str(item) for item in borrowed_patterns],
        "stages": stages,
        "safety_invariants": [
            "Generated model output is draft-only until review.",
            "Model switching changes drafting/review behavior only; it does not approve final outputs.",
            "Uncertain, degraded, or failed outputs remain needs_human_review.",
            "Every run should preserve request, backend, source, review_gate, and artifact paths.",
            "Failed branches and low-quality outputs are inspectable assets, not silently overwritten.",
        ],
    }


def render_model_architecture_summary(plan: dict[str, Any]) -> str:
    lines = [
        "Review-Gated Model Architecture",
        "",
        f"Architecture mode: {plan.get('architecture_mode', 'review_gated_local')}",
        f"Task type: {plan.get('task_type', 'research_draft')}",
        f"Source count: {plan.get('source_count', 0)}",
        f"Primary backend: {plan.get('primary_backend')} "
        f"(effective model: {plan.get('primary_model', {}).get('effective_model', 'none')})",
        f"Review backend: {plan.get('review_backend')} "
        f"(effective model: {plan.get('review_model', {}).get('effective_model', 'none')})",
        f"Fallback enabled: {plan.get('fallback_enabled')}",
        f"Auto-finalization enabled: {plan.get('auto_finalize_enabled')}",
        f"Human review required by policy: {plan.get('review_required_by_policy')}",
        "",
        "Borrowed patterns kept local:",
    ]
    lines.extend(f"- {item}" for item in plan.get("borrowed_patterns", []))
    lines.extend(["", "Execution stages:"])
    for stage in plan.get("stages", []):
        lines.append(
            "- {stage_id}: {role} via {backend} | {purpose}".format(
                stage_id=stage.get("stage_id", "stage"),
                role=stage.get("role", "role"),
                backend=stage.get("backend", "backend"),
                purpose=stage.get("purpose", ""),
            )
        )
    lines.extend(["", "Safety invariants:"])
    lines.extend(f"- {item}" for item in plan.get("safety_invariants", []))
    return "\n".join(lines)
