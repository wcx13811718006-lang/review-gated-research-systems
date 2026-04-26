from __future__ import annotations

from typing import Any


def evaluate_local_answer(
    answer: str,
    source_context: str,
    backend_status: dict[str, Any],
    quality_config: dict[str, Any],
) -> dict[str, Any]:
    minimum_answer = int(quality_config.get("minimum_answer_characters", 120))
    minimum_context = int(quality_config.get("minimum_source_context_characters", 200))
    allow_final = bool(quality_config.get("allow_final_without_review", False))
    require_review = bool(quality_config.get("require_human_review", True))
    reasoning_only = answer.startswith("LM Studio returned reasoning content without a final answer.")

    checks = [
        {
            "name": "answer_present",
            "passed": len(answer.strip()) >= minimum_answer,
            "detail": f"Answer characters: {len(answer.strip())}; required: {minimum_answer}.",
        },
        {
            "name": "final_answer_present",
            "passed": bool(answer.strip()) and not reasoning_only,
            "detail": "Reasoning-only model output is not treated as a usable final answer.",
        },
        {
            "name": "source_context_present",
            "passed": len(source_context.strip()) >= minimum_context,
            "detail": f"Source-context characters: {len(source_context.strip())}; required: {minimum_context}.",
        },
        {
            "name": "backend_reachable",
            "passed": bool(backend_status.get("reachable")),
            "detail": str(backend_status.get("status_label", "")),
        },
        {
            "name": "human_review_required",
            "passed": require_review,
            "detail": "Local model output remains draft material until reviewed.",
        },
    ]
    failed = [check["name"] for check in checks if not check["passed"]]
    review_required = require_review or bool(failed) or not allow_final

    return {
        "decision": "needs_human_review" if review_required else "approved_for_analysis",
        "review_required": review_required,
        "can_export_final": not review_required,
        "failed_checks": failed,
        "checks": checks,
        "accuracy_policy": (
            "The repository does not claim model-perfect accuracy. It guarantees that "
            "local-model output is treated as draft material unless it clears explicit "
            "validation and human review."
        ),
    }
